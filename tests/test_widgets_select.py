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
    clicked = []

    async def on_click(event, widget, manager, item_id):
        clicked.append(item_id)

    sel = Select(Format("{item[name]}"), id="s", item_id_getter=GET_ID,
                 items="items", on_click=on_click)
    kb = await sel.render_keyboard(DATA, m)
    labels = [b.label for row in kb for b in row]
    cds = [b.callback_data for row in kb for b in row]
    assert labels == ["Один", "Два"] and cds == ["s:1", "s:2"]
    assert await sel.process_callback("s:2", m) is True
    assert clicked == ["2"]  # item_id приходит строкой


async def test_radio_str_contract(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    radio = Radio(Format("✓ {item[name]}"), Format("{item[name]}"), id="r",
                  item_id_getter=GET_ID, items="items", type_factory=int)
    await radio.process_callback("r:2", m)
    assert m.current_context().widget_data["r"] == "2"  # строка!
    managed = radio.managed(m)
    assert managed.get_checked() == 2  # type_factory на чтении
    assert managed.is_checked(2) and not managed.is_checked(1)
    kb = await radio.render_keyboard(DATA, m)
    assert [b.label for row in kb for b in row] == ["Один", "✓ Два"]


async def test_multiselect_min_max(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    ms = Multiselect(Format("✓{item[id]}"), Format("{item[id]}"), id="ms",
                     item_id_getter=GET_ID, items="items", max_selected=1)
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
