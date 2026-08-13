from vkbottle_dialog.api.entities import (
    KeyboardKind,
    NewMessage,
    ShowMode,
    Stack,
    make_stack_key,
)
from vkbottle_dialog.manager.message_manager import MessageManager

NOW = 1_000_000.0


def new_msg(
    text="t", kb='{"inline":true,"buttons":[]}', kind=KeyboardKind.INLINE, mode=ShowMode.AUTO
):
    return NewMessage(peer_id=5, text=text, keyboard=kb, keyboard_kind=kind, show_mode=mode)


def fresh_stack(**kw):
    defaults = dict(key=make_stack_key(1, 5, 5))
    defaults.update(kw)
    return Stack(**defaults)


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


async def test_remove_kbd(fake_api):
    mm = MessageManager(fake_api)
    stack = fresh_stack(
        last_cmid=50, last_message_sent_at=NOW - 100, last_keyboard_kind=KeyboardKind.INLINE
    )
    await mm.remove_kbd(stack, peer_id=5, now=NOW)
    edits = fake_api.sent("messages.edit")
    assert len(edits) == 1 and "keyboard" not in edits[0]
    assert stack.last_cmid is None
