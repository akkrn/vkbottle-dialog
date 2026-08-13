import json

from vkbottle_dialog.api.entities import (
    CarouselElement,
    CarouselSpec,
    KeyboardKind,
    MediaAttachment,
    NewMessage,
    ShowMode,
    Stack,
    make_stack_key,
)
from vkbottle_dialog.manager.media_resolver import MediaResolver
from vkbottle_dialog.manager.message_manager import MessageManager
from vkbottle_dialog.widgets.kbd.base import VKButton

NOW = 1_000_000.0


def new_msg(
    text="t", kb='{"inline":true,"buttons":[]}', kind=KeyboardKind.INLINE, mode=ShowMode.AUTO
):
    return NewMessage(peer_id=5, text=text, keyboard=kb, keyboard_kind=kind, show_mode=mode)


def fresh_stack(**kw):
    defaults = dict(key=make_stack_key(1, 5, 5))
    defaults.update(kw)
    return Stack(**defaults)


def carousel_msg(mode=ShowMode.AUTO, photo=None, n=2):
    elements = [
        CarouselElement(
            title=f"Товар {i}",
            description="описание",
            photo=photo,
            buttons=[VKButton(action="callback", label="Купить", callback_data=f"pay:{i}")],
        )
        for i in range(1, n + 1)
    ]
    return NewMessage(
        peer_id=5,
        text="Каталог",
        keyboard=None,
        keyboard_kind=KeyboardKind.NONE,
        carousel=CarouselSpec(elements=elements),
        show_mode=mode,
    )


class OkUploader:
    def __init__(self, api):
        self.calls = 0

    async def upload(self, file_source, peer_id=None, **kw):
        self.calls += 1
        return "photo1_1_key"


def make_resolver():
    up = OkUploader(None)
    return MediaResolver(
        api=None, photo_uploader_factory=lambda a: up, doc_uploader_factory=lambda a: up
    ), up


async def test_first_send(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack()
    await mm.show_message(new_msg(), stack, trigger="message_event", now=NOW)
    assert len(fake_api.sent("messages.send")) == 1
    assert stack.last_cmid == 101 and stack.last_message_sent_at == NOW
    assert stack.last_keyboard_kind is KeyboardKind.INLINE


async def test_callback_edits_fresh_window(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.INLINE,
        last_render_hash="old",
    )
    await mm.show_message(new_msg(), stack, trigger="message_event", now=NOW)
    edits = fake_api.sent("messages.edit")
    assert len(edits) == 1 and edits[0]["cmid"] == 50
    assert edits[0]["keyboard"]  # клавиатура передана обязательно
    assert stack.last_cmid == 50


async def test_unchanged_hash_skips(fake_api):
    mm = MessageManager(fake_api)
    msg = new_msg()
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.INLINE,
        last_render_hash=msg.render_hash(),
    )
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    assert fake_api.calls == []


async def test_old_window_sends_new(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50, last_message_sent_at=NOW - 90_000, last_keyboard_kind=KeyboardKind.INLINE
    )
    await mm.show_message(new_msg(), stack, trigger="message_event", now=NOW)
    assert fake_api.sent("messages.edit") == []
    assert stack.last_cmid == 101


async def test_message_trigger_sends_and_strips_old_kbd(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.INLINE,
        last_render_hash="x",
    )
    await mm.show_message(new_msg(), stack, trigger="message_new", now=NOW)
    edits = fake_api.sent("messages.edit")
    assert len(edits) == 1 and "keyboard" not in edits[0]  # снятие кнопок
    assert len(fake_api.sent("messages.send")) == 1
    assert stack.last_cmid == 101


async def test_edit_fail_falls_back_to_send(fake_api):
    fake_api.fail_edit_with = 909
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50, last_message_sent_at=NOW - 100, last_keyboard_kind=KeyboardKind.INLINE
    )
    await mm.show_message(new_msg(), stack, trigger="message_event", now=NOW)
    assert len(fake_api.sent("messages.send")) == 1
    assert fake_api.sent("messages.delete") == []  # без удаления (спека §6.4)
    assert stack.last_cmid == 101


async def test_explicit_delete_and_send(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50, last_message_sent_at=NOW - 100, last_keyboard_kind=KeyboardKind.INLINE
    )
    await mm.show_message(
        new_msg(mode=ShowMode.DELETE_AND_SEND), stack, trigger="message_event", now=NOW
    )
    deletes = fake_api.sent("messages.delete")
    assert len(deletes) == 1 and deletes[0]["cmids"] == [50]
    assert stack.last_cmid == 101


async def test_text_kbd_transition_deletes(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50, last_message_sent_at=NOW - 100, last_keyboard_kind=KeyboardKind.TEXT
    )
    await mm.show_message(new_msg(), stack, trigger="message_event", now=NOW)
    assert len(fake_api.sent("messages.delete")) == 1
    assert len(fake_api.sent("messages.send")) == 1


TEXT_KB = '{"one_time":false,"inline":false,"buttons":[]}'


async def test_text_kbd_unchanged_message_event_edits(fake_api):
    mm = MessageManager(fake_api)
    msg = new_msg(kb=TEXT_KB, kind=KeyboardKind.TEXT)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.TEXT,
        last_kb_hash=msg.kb_hash(),
    )
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    edits = fake_api.sent("messages.edit")
    assert len(edits) == 1 and "keyboard" not in edits[0]
    assert fake_api.sent("messages.delete") == []
    assert fake_api.sent("messages.send") == []
    assert stack.last_cmid == 50
    assert stack.last_kb_hash == msg.kb_hash()


async def test_text_kbd_changed_message_event_deletes(fake_api):
    mm = MessageManager(fake_api)
    msg = new_msg(kb=TEXT_KB, kind=KeyboardKind.TEXT)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.TEXT,
        last_kb_hash="different-hash",
    )
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    assert len(fake_api.sent("messages.delete")) == 1
    assert len(fake_api.sent("messages.send")) == 1
    assert stack.last_kb_hash == msg.kb_hash()


async def test_text_kbd_unchanged_message_new_still_deletes(fake_api):
    mm = MessageManager(fake_api)
    msg = new_msg(kb=TEXT_KB, kind=KeyboardKind.TEXT)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.TEXT,
        last_kb_hash=msg.kb_hash(),
    )
    await mm.show_message(msg, stack, trigger="message_new", now=NOW)
    assert len(fake_api.sent("messages.delete")) == 1
    assert len(fake_api.sent("messages.send")) == 1


async def test_explicit_edit_text_kbd_changed_includes_keyboard(fake_api):
    # ShowMode.EDIT явно запрошен вызывающим кодом (update/switch_to/
    # Button(show_mode=...)), а не выведен AUTO — клавиатура ИЗМЕНИЛАСЬ
    # (last_kb_hash не совпадает с новой), значит её обязательно нужно
    # передать в messages.edit, иначе новая клавиатура никогда не применится.
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.TEXT,
        last_kb_hash="different-hash",
    )
    msg = new_msg(kb=TEXT_KB, kind=KeyboardKind.TEXT, mode=ShowMode.EDIT)
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    edits = fake_api.sent("messages.edit")
    assert len(edits) == 1 and edits[0].get("keyboard") == TEXT_KB
    assert stack.last_kb_hash == msg.kb_hash()


async def test_text_kbd_unchanged_but_stale_deletes_instead_of_edit(fake_api):
    # Окно старше окна редактирования VK (23.5ч запас к лимиту 24ч) — даже
    # при неизменной нижней клавиатуре и message_event нельзя молча
    # свалиться в bare _send (оставив старое окно висеть): должно быть
    # DELETE_AND_SEND, как раньше для любого TEXT-кейса.
    mm = MessageManager(fake_api)
    msg = new_msg(kb=TEXT_KB, kind=KeyboardKind.TEXT)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 90_000,  # > EDIT_WINDOW_SECONDS
        last_keyboard_kind=KeyboardKind.TEXT,
        last_kb_hash=msg.kb_hash(),
    )
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    assert len(fake_api.sent("messages.delete")) == 1
    assert len(fake_api.sent("messages.send")) == 1
    assert fake_api.sent("messages.edit") == []


async def test_remove_kbd(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50, last_message_sent_at=NOW - 100, last_keyboard_kind=KeyboardKind.INLINE
    )
    await mm.remove_kbd(stack, peer_id=5, now=NOW)
    edits = fake_api.sent("messages.edit")
    assert len(edits) == 1 and "keyboard" not in edits[0]
    assert stack.last_cmid is None


async def test_first_send_with_carousel_includes_template(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack()
    await mm.show_message(carousel_msg(), stack, trigger="message_new", now=NOW)
    sent = fake_api.sent("messages.send")[0]
    assert sent["message"] == "Каталог"
    template = json.loads(sent["template"])
    assert template["type"] == "carousel"
    assert len(template["elements"]) == 2
    el = template["elements"][0]
    assert el["title"] == "Товар 1" and el["description"] == "описание"
    assert el["buttons"][0]["action"]["payload"] == "pay:1"
    assert "photo_id" not in el
    assert stack.last_had_carousel is True


async def test_carousel_photo_resolved_to_photo_id(fake_api):
    resolver, up = make_resolver()
    mm = MessageManager(fake_api, media_resolver=resolver)
    stack = fresh_stack()
    msg = carousel_msg(photo=MediaAttachment(attachment="photo9_9_zzz"), n=1)
    await mm.show_message(msg, stack, trigger="message_new", now=NOW)
    sent = fake_api.sent("messages.send")[0]
    template = json.loads(sent["template"])
    assert template["elements"][0]["photo_id"] == "9_9"
    assert up.calls == 0  # attachment уже готов — аплоуд не нужен


async def test_carousel_to_inline_transition_deletes_and_sends(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.NONE,
        last_had_carousel=True,
    )
    await mm.show_message(new_msg(), stack, trigger="message_event", now=NOW)
    assert len(fake_api.sent("messages.delete")) == 1
    assert len(fake_api.sent("messages.send")) == 1
    assert stack.last_had_carousel is False


async def test_inline_to_carousel_transition_deletes_and_sends(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.INLINE,
        last_had_carousel=False,
    )
    await mm.show_message(carousel_msg(), stack, trigger="message_event", now=NOW)
    assert len(fake_api.sent("messages.delete")) == 1
    assert len(fake_api.sent("messages.send")) == 1
    assert stack.last_had_carousel is True


async def test_carousel_unchanged_edits_with_template(fake_api):
    mm = MessageManager(fake_api)
    msg = carousel_msg()
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.NONE,
        last_had_carousel=True,
        last_render_hash="old",
    )
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    edits = fake_api.sent("messages.edit")
    assert len(edits) == 1
    template = json.loads(edits[0]["template"])
    assert template["type"] == "carousel"
    assert fake_api.sent("messages.delete") == []
    assert stack.last_had_carousel is True


async def test_no_resolver_photo_carousel_not_marked_failed(fake_api):
    # media_resolver=None — конфигурационный выбор, а не сбой аплоуда:
    # photo_id просто не проставляется, но render_hash НЕ должен получать
    # "carousel:failed"-маркер (иначе идентичный повторный рендер никогда
    # не хэш-скипнется и будет вечно уходить в edit).
    mm = MessageManager(fake_api)  # без media_resolver
    msg = carousel_msg(photo=MediaAttachment(path="a.png"), n=1)
    stack = fresh_stack()
    await mm.show_message(msg, stack, trigger="message_new", now=NOW)
    sent = fake_api.sent("messages.send")[0]
    template = json.loads(sent["template"])
    assert "photo_id" not in template["elements"][0]
    assert stack.last_render_hash == msg.render_hash()  # без "carousel:failed"

    # повторный идентичный рендер — hash-скип, без нового вызова API
    fake_api.calls.clear()
    stack.last_message_sent_at = NOW
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    assert fake_api.calls == []


async def test_explicit_edit_carousel_to_inline_deletes_and_sends(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50,
        last_message_sent_at=NOW - 100,
        last_keyboard_kind=KeyboardKind.NONE,
        last_had_carousel=True,
    )
    msg = new_msg(mode=ShowMode.EDIT)  # carousel=None, явный EDIT в обход AUTO
    await mm.show_message(msg, stack, trigger="message_event", now=NOW)
    assert len(fake_api.sent("messages.delete")) == 1
    assert len(fake_api.sent("messages.send")) == 1
    assert fake_api.sent("messages.edit") == []
    assert stack.last_had_carousel is False
