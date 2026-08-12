from vkbottle_dialog.api.entities import (
    KeyboardKind,
    MediaAttachment,
    NewMessage,
    ShowMode,
    Stack,
    make_stack_key,
)
from vkbottle_dialog.manager.media_resolver import MediaResolver
from vkbottle_dialog.manager.message_manager import MessageManager

NOW = 1_000_000.0


class OkUploader:
    def __init__(self, api):
        self.calls = 0

    async def upload(self, file_source, peer_id=None, **kw):
        self.calls += 1
        return "photo1_1_k"


def make_resolver(tmp_path, uploader_cls=OkUploader):
    up = uploader_cls(None)
    return MediaResolver(
        api=None, photo_uploader_factory=lambda a: up, doc_uploader_factory=lambda a: up
    ), up


def media_msg(tmp_path, mode=ShowMode.AUTO):
    f = tmp_path / "a.png"
    if not f.exists():
        f.write_bytes(b"x")
    return NewMessage(
        peer_id=5,
        text="t",
        keyboard=None,
        keyboard_kind=KeyboardKind.NONE,
        media=MediaAttachment(path=str(f)),
        show_mode=mode,
    )


def fresh_stack(**kw):
    d = dict(key=make_stack_key(1, 5, 5))
    d.update(kw)
    return Stack(**d)


async def test_send_with_media(fake_api, tmp_path):
    resolver, up = make_resolver(tmp_path)
    mm = MessageManager(fake_api, media_resolver=resolver)
    stack = fresh_stack()
    msg = media_msg(tmp_path)
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    sent = fake_api.sent("messages.send")[0]
    assert sent["attachment"] == "photo1_1_k"
    assert stack.last_media_key == msg.media.source_key()
    assert stack.last_render_hash == msg.render_hash()


async def test_hash_skip_does_not_upload(fake_api, tmp_path):
    resolver, up = make_resolver(tmp_path)
    mm = MessageManager(fake_api, media_resolver=resolver)
    msg = media_msg(tmp_path)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 10,
        last_keyboard_kind=KeyboardKind.NONE,
        last_render_hash=msg.render_hash(),
    )
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    assert fake_api.calls == [] and up.calls == 0


async def test_degradation_stamps_retry_hash(fake_api, tmp_path):
    class Boom:
        def __init__(self, api): ...
        async def upload(self, *a, **kw):
            raise RuntimeError("down")

    resolver, _ = make_resolver(tmp_path, Boom)
    mm = MessageManager(fake_api, media_resolver=resolver)
    stack = fresh_stack()
    msg = media_msg(tmp_path)
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    sent = fake_api.sent("messages.send")[0]
    assert "attachment" not in sent  # окно ушло без медиа
    assert stack.last_media_key is None
    assert stack.last_render_hash != msg.render_hash()  # анти-локаут: ретрай будет


async def test_edit_clears_removed_media(fake_api, tmp_path):
    resolver, _ = make_resolver(tmp_path)
    mm = MessageManager(fake_api, media_resolver=resolver)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 10,
        last_keyboard_kind=KeyboardKind.NONE,
        last_media_key="photo|old.png",
        last_render_hash="old",
    )
    no_media = NewMessage(peer_id=5, text="t2", keyboard=None, keyboard_kind=KeyboardKind.NONE)
    await mm.show_message(no_media, stack, trigger="message_event", now=NOW)
    edit = fake_api.sent("messages.edit")[0]
    assert edit["attachment"] == ""  # явная очистка
    assert stack.last_media_key is None


async def test_no_resolver_ignores_media(fake_api, tmp_path):
    mm = MessageManager(fake_api)  # media_resolver=None
    stack = fresh_stack()
    await mm.show_message(media_msg(tmp_path), stack, trigger="message_event", now=NOW)
    assert "attachment" not in fake_api.sent("messages.send")[0]
