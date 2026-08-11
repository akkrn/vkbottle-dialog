import pytest
from vkbottle_dialog.api.entities import (
    Context, EventContext, KeyboardKind, NewMessage, Stack,
    make_stack_key, new_intent_id,
)
from vkbottle_dialog.exceptions import DialogStackOverflow
from vkbottle_dialog.fsm import State, StatesGroup


class SG(StatesGroup):
    a = State()


def make_stack() -> Stack:
    return Stack(key=make_stack_key(1, 2, 2))


def test_intent_id_unique_and_len():
    ids = {new_intent_id() for _ in range(200)}
    assert len(ids) == 200
    assert all(len(i) == 11 and i.isalnum() for i in ids)


def test_stack_key_format():
    assert make_stack_key(10, 20, 30) == "vkd:stack:10:20:30:0"


def test_push_pop_and_overflow():
    stack = make_stack()
    ctx = stack.push(SG.a, {"x": 1})
    assert stack.last_intent_id() == ctx.intent_id
    assert ctx.stack_key == stack.key and ctx.start_data == {"x": 1}
    assert stack.pop() == ctx.intent_id and stack.empty()
    for _ in range(100):
        stack.push(SG.a, None)
    with pytest.raises(DialogStackOverflow):
        stack.push(SG.a, None)


def test_context_identity():
    stack = make_stack()
    c1 = stack.push(SG.a, None)
    c2 = Context(intent_id=c1.intent_id, stack_key=c1.stack_key, state=SG.a,
                 start_data=None, dialog_data={"changed": True}, widget_data={})
    assert c1.same(c2)


def test_event_context_chat_detection():
    ev = EventContext(group_id=1, peer_id=2_000_000_005, owner_id=77, user_id=77,
                     kind="message_event", raw=None)
    assert ev.is_chat and ev.stack_key == "vkd:stack:1:2000000005:77:0"
    ls = EventContext(group_id=1, peer_id=55, owner_id=55, user_id=55,
                      kind="message_new", raw=None)
    assert not ls.is_chat


def test_render_hash_changes():
    m1 = NewMessage(peer_id=1, text="a", keyboard=None,
                    keyboard_kind=KeyboardKind.NONE, attachments=[])
    m2 = NewMessage(peer_id=1, text="b", keyboard=None,
                    keyboard_kind=KeyboardKind.NONE, attachments=[])
    assert m1.render_hash() != m2.render_hash()
    assert m1.render_hash() == NewMessage(peer_id=9, text="a", keyboard=None,
                                          keyboard_kind=KeyboardKind.NONE,
                                          attachments=[]).render_hash()
