import asyncio

import pytest

from vkbottle_dialog.api.entities import MediaAttachment
from vkbottle_dialog.context.memory import MemoryStorage
from vkbottle_dialog.manager.media_resolver import MEDIA_CACHE_MAXSIZE, MediaResolver


class FakeUploader:
    def __init__(self, api):
        self.calls = []

    async def upload(self, file_source, peer_id=None, **kw):
        self.calls.append((file_source, peer_id, kw))
        return f"photo1_{len(self.calls)}_key"


class SlowUploader:
    def __init__(self, api):
        self.calls = []

    async def upload(self, file_source, peer_id=None, **kw):
        await asyncio.sleep(0.05)
        self.calls.append((file_source, peer_id, kw))
        return f"photo1_{len(self.calls)}_key"


@pytest.fixture
def resolver(tmp_path):
    uploader = FakeUploader(None)
    r = MediaResolver(
        api=None,
        photo_uploader_factory=lambda api: uploader,
        doc_uploader_factory=lambda api: uploader,
    )
    return r, uploader, tmp_path


async def test_ready_attachment_passthrough(resolver):
    r, uploader, _ = resolver
    out = await r.resolve(MediaAttachment(attachment="photo9_9_z"), peer_id=1)
    assert out == "photo9_9_z" and uploader.calls == []


async def test_path_upload_and_cache_hit(resolver):
    r, uploader, tmp = resolver
    f = tmp / "a.png"
    f.write_bytes(b"x")
    media = MediaAttachment(path=str(f))
    first = await r.resolve(media, peer_id=1)
    second = await r.resolve(media, peer_id=2)  # фото: кэш пере-peer
    assert first == second and len(uploader.calls) == 1


async def test_mtime_invalidates(resolver):
    r, uploader, tmp = resolver
    f = tmp / "a.png"
    f.write_bytes(b"x")
    media = MediaAttachment(path=str(f))
    await r.resolve(media, peer_id=1)
    import os

    os.utime(f, (1, 1))  # смена mtime
    await r.resolve(media, peer_id=1)
    assert len(uploader.calls) == 2


async def test_doc_cache_is_peer_scoped(resolver):
    r, uploader, tmp = resolver
    f = tmp / "a.pdf"
    f.write_bytes(b"x")
    media = MediaAttachment(path=str(f), type="doc")
    await r.resolve(media, peer_id=1)
    await r.resolve(media, peer_id=2)
    assert len(uploader.calls) == 2  # doc: peer в ключе
    assert uploader.calls[0][2].get("title") == "a.pdf"  # basename как title


async def test_failure_degrades_to_none(resolver, tmp_path):
    class Boom:
        def __init__(self, api): ...
        async def upload(self, *a, **kw):
            raise RuntimeError("vk down")

    r = MediaResolver(api=None, photo_uploader_factory=Boom, doc_uploader_factory=Boom)
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    assert await r.resolve(MediaAttachment(path=str(f)), peer_id=1) is None


async def test_storage_round_trip_across_instances(tmp_path):
    uploader = FakeUploader(None)
    storage = MemoryStorage()
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    media = MediaAttachment(path=str(f))

    r1 = MediaResolver(
        api=None,
        storage=storage,
        photo_uploader_factory=lambda api: uploader,
        doc_uploader_factory=lambda api: uploader,
    )
    first = await r1.resolve(media, peer_id=1)
    assert len(uploader.calls) == 1

    # fresh resolver instance -> empty in-memory cache, same storage
    r2 = MediaResolver(
        api=None,
        storage=storage,
        photo_uploader_factory=lambda api: uploader,
        doc_uploader_factory=lambda api: uploader,
    )
    second = await r2.resolve(media, peer_id=1)
    assert second == first
    assert len(uploader.calls) == 1  # no new upload, storage hit


async def test_broken_storage_degrades_but_upload_succeeds(tmp_path):
    class BrokenStorage:
        async def get(self, key):
            raise RuntimeError("storage down")

        async def set(self, key, data):
            raise RuntimeError("storage down")

        async def delete(self, key):
            raise RuntimeError("storage down")

        async def touch(self, *keys):
            raise RuntimeError("storage down")

    uploader = FakeUploader(None)
    r = MediaResolver(
        api=None,
        storage=BrokenStorage(),
        photo_uploader_factory=lambda api: uploader,
        doc_uploader_factory=lambda api: uploader,
    )
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    media = MediaAttachment(path=str(f))

    result = await r.resolve(media, peer_id=1)
    assert result == "photo1_1_key"
    assert len(uploader.calls) == 1


async def test_concurrent_resolve_same_key_uploads_once(tmp_path):
    uploader = SlowUploader(None)
    r = MediaResolver(
        api=None,
        photo_uploader_factory=lambda api: uploader,
        doc_uploader_factory=lambda api: uploader,
    )
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    media = MediaAttachment(path=str(f))

    first, second = await asyncio.gather(r.resolve(media, peer_id=1), r.resolve(media, peer_id=1))
    assert first == second
    assert len(uploader.calls) == 1


async def test_cache_is_bounded_lru(tmp_path):
    uploader = FakeUploader(None)
    r = MediaResolver(
        api=None,
        photo_uploader_factory=lambda api: uploader,
        doc_uploader_factory=lambda api: uploader,
    )
    paths = []
    for i in range(MEDIA_CACHE_MAXSIZE + 1):
        f = tmp_path / f"f{i}.png"
        f.write_bytes(b"x")
        paths.append(str(f))

    for path in paths:
        await r.resolve(MediaAttachment(path=path), peer_id=1)

    assert len(r._cache) <= MEDIA_CACHE_MAXSIZE
    oldest_key = r._cache_key(MediaAttachment(path=paths[0]), peer_id=1)
    assert oldest_key not in r._cache


async def test_corrupt_non_dict_storage_doc_degrades_but_upload_succeeds(tmp_path):
    class CorruptStorage:
        async def get(self, key):
            return "not-a-dict"  # повреждённые данные вместо {"attachment": ...}

        async def set(self, key, data): ...

        async def delete(self, key): ...

        async def touch(self, *keys): ...

    uploader = FakeUploader(None)
    r = MediaResolver(
        api=None,
        storage=CorruptStorage(),
        photo_uploader_factory=lambda api: uploader,
        doc_uploader_factory=lambda api: uploader,
    )
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    media = MediaAttachment(path=str(f))

    result = await r.resolve(media, peer_id=1)
    assert result == "photo1_1_key"
    assert len(uploader.calls) == 1
