import pytest

from vkbottle_dialog.api.entities import EventContext, KeyboardKind
from vkbottle_dialog.dialog import Dialog
from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.input import TextInput
from vkbottle_dialog.widgets.kbd import Button, ScrollingGroup
from vkbottle_dialog.widgets.markup import InlineKeyboardFactory, TextKeyboardFactory
from vkbottle_dialog.widgets.text import Const, Format
from vkbottle_dialog.window import Window


class SG(StatesGroup):
    first = State()
    second = State()


class OtherSG(StatesGroup):
    x = State()


def ls_event():
    return EventContext(group_id=1, peer_id=5, owner_id=5, user_id=5,
                        kind="message_new", raw=None)


def chat_event():
    return EventContext(group_id=1, peer_id=2_000_000_001, owner_id=7, user_id=7,
                        kind="message_new", raw=None)


class RenderManager:
    """FakeManager с load_data для рендера (см. conftest — расширить базовый)."""
    def __init__(self, ctx):
        self._ctx = ctx
        self.event = None

    def current_context(self):
        return self._ctx

    async def load_data(self):
        return {"dialog_data": self._ctx.dialog_data, "start_data": self._ctx.start_data}


async def test_window_render(fake_manager_factory):
    win = Window(
        "Привет, ",  # str → Const
        Format("{name}!"),
        Button(Const("Ok"), id="ok"),
        state=SG.first,
        getter={"name": "Вася"},
    )
    dlg = Dialog(win, Window(Const("2"), state=SG.second))
    from vkbottle_dialog.api.entities import Stack, make_stack_key
    stack = Stack(key=make_stack_key(1, 5, 5))
    ctx = stack.push(SG.first, None)
    m = RenderManager(ctx)
    msg = await dlg.render(m, ls_event(), ctx.intent_id, None, InlineKeyboardFactory())
    assert msg.text == "Привет, \nВася!"
    assert msg.keyboard_kind is KeyboardKind.INLINE and "Ok" in msg.keyboard


async def test_text_keyboard_forbidden_in_chat():
    win = Window(Const("x"), Button(Const("b"), id="b"), state=SG.first,
                 markup_factory=TextKeyboardFactory())
    dlg = Dialog(win, Window(Const("2"), state=SG.second))
    from vkbottle_dialog.api.entities import Stack, make_stack_key
    stack = Stack(key=make_stack_key(1, 2_000_000_001, 7))
    ctx = stack.push(SG.first, None)
    with pytest.raises(DialogConfigError):
        await dlg.render(RenderManager(ctx), chat_event(), ctx.intent_id, None,
                         InlineKeyboardFactory())


def test_dialog_validation():
    with pytest.raises(DialogConfigError):
        Dialog()
    with pytest.raises(DialogConfigError):
        Dialog(Window(Const("a"), state=SG.first),
               Window(Const("b"), state=OtherSG.x))
    with pytest.raises(DialogConfigError):
        Dialog(Window(Const("a"), state=SG.first),
               Window(Const("b"), state=SG.first))


def test_dialog_states_and_window_for():
    dlg = Dialog(Window(Const("a"), state=SG.first),
                 Window(Const("b"), state=SG.second))
    assert dlg.states() == (SG.first, SG.second)
    assert dlg.states_group() is SG
    assert dlg.window_for(SG.second) is not None


async def test_find_and_scroll():
    dlg = Dialog(
        Window(Const("a"),
               ScrollingGroup(Button(Const("1"), id="b1"), id="sc", height=1),
               TextInput(id="ti"),
               state=SG.first),
        Window(Const("b"), state=SG.second),
    )
    assert dlg.find("sc").widget_id == "sc"
    assert dlg.find("ti").widget_id == "ti"
    assert dlg.find("nope") is None
