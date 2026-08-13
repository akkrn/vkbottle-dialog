import pytest

from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import Button, Checkbox, ListGroup, NumberedPager
from vkbottle_dialog.widgets.text import Const
from vkbottle_dialog.window import Window


class SG(StatesGroup):
    a = State()


def get_id(item):
    return item["id"]


ITEMS = [{"id": "1"}, {"id": "2"}, {"id": "3"}]


def make_list_group(items=ITEMS, page_size=0, item_id_getter=get_id, **kw):
    return ListGroup(
        Checkbox(Const("[x]"), Const("[ ]"), id="chk"),
        Button(Const("del"), id="btn"),
        id="lg",
        item_id_getter=item_id_getter,
        items="items",
        page_size=page_size,
        **kw,
    )


async def test_render_prefixes_callback_data_per_row(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    lg = make_list_group()
    kb = await lg.render_keyboard({"items": ITEMS}, m)
    cds = [btn.callback_data for row in kb for btn in row]
    assert cds == [
        "lg:1:chk",
        "lg:1:btn",
        "lg:2:chk",
        "lg:2:btn",
        "lg:3:chk",
        "lg:3:btn",
    ]


async def test_click_toggles_checkbox_only_in_its_own_row(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    lg = make_list_group()
    data = {"items": ITEMS}
    await lg.render_keyboard(data, m)  # прогреваем widget_data строк

    handled = await lg.process_callback("lg:2:chk", m)

    assert handled is True
    assert m.current_context().widget_data["lg"]["2"]["chk"] is True
    assert m.current_context().widget_data["lg"].get("1", {}).get("chk") is not True
    assert m.current_context().widget_data["lg"].get("3", {}).get("chk") is not True


async def test_item_id_with_colon_raises_dialog_config_error(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    bad_items = [{"id": "a:b"}]
    lg = make_list_group(items=bad_items)
    with pytest.raises(DialogConfigError):
        await lg.render_keyboard({"items": bad_items}, m)


async def test_find_recurses_into_child_buttons():
    lg = make_list_group()
    assert lg.find("lg") is lg
    found = lg.find("chk")
    assert found is not None and found.widget_id == "chk"
    assert lg.find("missing") is None


async def test_managed_find_for_item_scopes_state_to_row(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    lg = make_list_group()
    await lg.render_keyboard({"items": ITEMS}, m)
    await lg.process_callback("lg:2:chk", m)

    managed = lg.managed(m).find_for_item("chk", "2")

    assert managed is not None
    assert managed.is_checked() is True

    other = lg.managed(m).find_for_item("chk", "1")
    assert other.is_checked() is False


async def test_pager_via_find_scroll_does_not_crash_and_moves_page(fake_manager_factory):
    # Регрессия на баг из спеки §1.2: BaseScroll.get_page делает
    # int(widget_data[id]), но у ListGroup там лежит dict (строки по
    # item_id) — без переопределения get_page/set_page первый же рендер
    # пейджера, привязанного к ListGroup, падает с int(dict) TypeError.
    m = fake_manager_factory(SG.a)
    items = [{"id": str(i)} for i in range(1, 6)]  # 5 штук
    m._data = {"items": items}
    lg = make_list_group(items=items, page_size=2)
    pager = NumberedPager(scroll_id="lg", id="pgr")
    win = Window(Const("t"), lg, pager, state=SG.a)
    m.find_scroll = win.find_scroll

    # Рендер уже прогревает widget_data["lg"] как dict (строки item_id) —
    # если бы пейджер не был переопределён, get_page(dict) уже упал бы тут.
    kb = await win._keyboard.render_keyboard(m._data, m)
    row_cds = [btn.callback_data for row in kb[:-1] for btn in row]
    assert row_cds == ["lg:1:chk", "lg:1:btn", "lg:2:chk", "lg:2:btn"]
    pager_row = kb[-1]
    assert [btn.callback_data for btn in pager_row] == ["pgr:0", "pgr:1", "pgr:2"]

    handled = await win.process_callback("pgr:1", m)
    assert handled is True
    assert lg.get_page(m) == 1

    kb2 = await win._keyboard.render_keyboard(m._data, m)
    row_cds2 = [btn.callback_data for row in kb2[:-1] for btn in row]
    assert row_cds2 == ["lg:3:chk", "lg:3:btn", "lg:4:chk", "lg:4:btn"]
