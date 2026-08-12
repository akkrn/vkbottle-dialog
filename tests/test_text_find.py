from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.text import Case, Const, Multi, Or
from vkbottle_dialog.window import Window


class SG(StatesGroup):
    a = State()


class FakeIdText(Const):
    """Текст с id — суррогат будущего List(page_size)."""

    def __init__(self, text, id):
        super().__init__(text)
        self.widget_id = id

    def find(self, widget_id):
        return self if widget_id == self.widget_id else None


def test_plain_text_find_none():
    assert Const("x").find("anything") is None


def test_containers_recurse():
    target = FakeIdText("t", id="tgt")
    assert Multi(Const("a"), target).find("tgt") is target
    assert Or(Const("a"), target).find("tgt") is target
    assert Case({1: target, ...: Const("d")}, selector="k").find("tgt") is target
    assert Multi(Const("a")).find("tgt") is None


def test_window_finds_in_text_slot():
    target = FakeIdText("t", id="tgt")
    win = Window(Const("head"), target, state=SG.a)
    assert win.find("tgt") is target
    assert win.find("nope") is None
