import operator

from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import Checkbox, Multiselect, Radio, Select, Toggle
from vkbottle_dialog.widgets.text import Const, Format


class SG(StatesGroup):
    a = State()


ITEMS = [{"id": 1, "name": "Один"}, {"id": 2, "name": "Два"}]
GET_ID = operator.itemgetter("id")
DATA = {"items": ITEMS}


async def test_select_render_and_click(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    m._data = DATA  # process_callback валидирует item_id против load_data()
    clicked = []

    async def on_click(event, widget, manager, item_id):
        clicked.append(item_id)

    sel = Select(
        Format("{item[name]}"), id="s", item_id_getter=GET_ID, items="items", on_click=on_click
    )
    kb = await sel.render_keyboard(DATA, m)
    labels = [b.label for row in kb for b in row]
    cds = [b.callback_data for row in kb for b in row]
    assert labels == ["Один", "Два"] and cds == ["s:1", "s:2"]
    assert await sel.process_callback("s:2", m) is True
    assert clicked == ["2"]  # item_id приходит строкой


async def test_radio_str_contract(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    m._data = DATA
    radio = Radio(
        Format("✓ {item[name]}"),
        Format("{item[name]}"),
        id="r",
        item_id_getter=GET_ID,
        items="items",
        type_factory=int,
    )
    await radio.process_callback("r:2", m)
    assert m.current_context().widget_data["r"] == "2"  # строка!
    managed = radio.managed(m)
    assert managed.get_checked() == 2  # type_factory на чтении
    assert managed.is_checked(2) and not managed.is_checked(1)
    kb = await radio.render_keyboard(DATA, m)
    assert [b.label for row in kb for b in row] == ["Один", "✓ Два"]


async def test_multiselect_min_max(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    m._data = DATA
    ms = Multiselect(
        Format("✓{item[id]}"),
        Format("{item[id]}"),
        id="ms",
        item_id_getter=GET_ID,
        items="items",
        max_selected=1,
    )
    await ms.process_callback("ms:1", m)
    await ms.process_callback("ms:2", m)  # max=1 — игнор
    assert m.current_context().widget_data["ms"] == ["1"]
    await ms.process_callback("ms:1", m)  # снятие
    assert m.current_context().widget_data["ms"] == []


async def test_toggle_cycles(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    t = Toggle(Format("{item}"), id="t", items=["a", "b"])
    kb = await t.render_keyboard({}, m)
    assert kb[0][0].label == "a"
    await t.process_callback("t", m)
    kb = await t.render_keyboard({}, m)
    assert kb[0][0].label == "b"


async def test_checkbox(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cb = Checkbox(Const("[x]"), Const("[ ]"), id="cb")
    kb = await cb.render_keyboard({}, m)
    assert kb[0][0].label == "[ ]"
    await cb.process_callback("cb", m)
    assert cb.managed(m).is_checked() is True


async def test_multiselect_blocked_uncheck_silent(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    m._data = DATA
    calls = []

    async def on_state_changed(event, widget, manager, item_id):
        calls.append(("on_state_changed", item_id))

    ms = Multiselect(
        Format("✓{item[id]}"),
        Format("{item[id]}"),
        id="ms",
        item_id_getter=GET_ID,
        items="items",
        min_selected=1,
        on_state_changed=on_state_changed,
    )
    # Check one item
    await ms.process_callback("ms:1", m)
    assert m.current_context().widget_data["ms"] == ["1"]
    assert len(calls) == 1
    calls.clear()
    # Try to uncheck the only item (blocked by min_selected=1)
    await ms.process_callback("ms:1", m)
    # widget_data must remain unchanged
    assert m.current_context().widget_data["ms"] == ["1"]
    # on_state_changed must not fire (silent no-op)
    assert calls == []


async def test_select_rejects_forged_item_id(fake_manager_factory):
    # FIX I3 (спека §5, шаг 6): item_id из callback_data может быть подделан
    # (произвольный id, не относящийся к текущему списку items) — виджет
    # обязан отвергнуть его молча, без записи в widget_data и без on_click.
    m = fake_manager_factory(SG.a)
    m._data = DATA  # items = [1, 2]
    clicked = []

    async def on_click(event, widget, manager, item_id):
        clicked.append(item_id)

    sel = Select(
        Format("{item[name]}"), id="s", item_id_getter=GET_ID, items="items", on_click=on_click
    )
    result = await sel.process_callback("s:999", m)
    assert result is False
    assert clicked == []


async def test_radio_rejects_forged_item_id(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    m._data = DATA
    radio = Radio(
        Format("✓ {item[name]}"),
        Format("{item[name]}"),
        id="r",
        item_id_getter=GET_ID,
        items="items",
    )
    result = await radio.process_callback("r:999", m)
    assert result is False
    assert "r" not in m.current_context().widget_data
