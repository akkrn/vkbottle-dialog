import pytest

from vkbottle_dialog.api.entities import MediaAttachment
from vkbottle_dialog.manager.media_resolver import MediaResolver


class FakeUploader:
    def __init__(self, api):
        self.calls = []

    async def upload(self, file_source, peer_id=None, **kw):
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
