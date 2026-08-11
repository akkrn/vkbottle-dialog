import pytest
from magic_filter import F

from vkbottle_dialog.api.entities import Stack, make_stack_key
from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.common import (
    Actionable,
    Whenable,
    ensure_data_getter,
    ensure_event_processor,
    get_items_getter,
)


class SG(StatesGroup):
    a = State()


class FakeManager:
    def __init__(self):
        stack = Stack(key=make_stack_key(1, 2, 2))
        self._ctx = stack.push(SG.a, None)

    def current_context(self):
        return self._ctx


def test_whenable_variants():
    m = FakeManager()
    assert Whenable().is_({}, m)
    assert Whenable(when="flag").is_({"flag": 1}, m)
    assert not Whenable(when="flag").is_({"flag": 0}, m)
    assert Whenable(when=F["n"] > 2).is_({"n": 3}, m)
    assert Whenable(when=lambda d, w, mg: d["ok"]).is_({"ok": True}, m)


def test_actionable_id_validation_and_data():
    with pytest.raises(DialogConfigError):
        Actionable(id="bad id!")
    w = Actionable(id="w1")
    m = FakeManager()
    assert w.get_widget_data(m, "def") == "def"
    w.set_widget_data(m, [1, 2])
    assert m.current_context().widget_data["w1"] == [1, 2]
    assert w.find("w1") is w and w.find("other") is None


async def test_event_processor():
    calls = []

    async def handler(event, widget, manager):
        calls.append(event)

    proc = ensure_event_processor(handler)
    await proc.process_event("ev", None, None)
    assert calls == ["ev"]
    await ensure_event_processor(None).process_event("ev", None, None)  # no-op


async def test_event_processor_sync_handler():
    calls = []

    def sync_handler(a, b, c):
        calls.append(a)

    proc = ensure_event_processor(sync_handler)
    await proc.process_event(1, 2, 3)
    assert calls == [1]


async def test_data_getters():
    g = ensure_data_getter(None)
    assert await g(x=1) == {}
    g = ensure_data_getter({"a": 1})
    assert await g() == {"a": 1}

    async def getter(dialog_manager=None, **kw):
        return {"b": 2}

    assert await ensure_data_getter(getter)(dialog_manager="m") == {"b": 2}


def test_items_getter():
    assert get_items_getter("items")({"items": [1, 2]}) == [1, 2]
    assert get_items_getter([3, 4])({}) == [3, 4]
    assert get_items_getter(lambda d: d["x"])({"x": [5]}) == [5]


def test_actionable_id_none_raises_on_data_access():
    w = Actionable(id=None)
    m = FakeManager()
    with pytest.raises(DialogConfigError):
        w.set_widget_data(m, 1)
    with pytest.raises(DialogConfigError):
        w.get_widget_data(m, "def")


async def test_sync_getter():
    def sync_getter(**kw):
        return {"b": 2}

    assert await ensure_data_getter(sync_getter)() == {"b": 2}
