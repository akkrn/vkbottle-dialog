import pytest

from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import (
    Button,
    Checkbox,
    ListGroup,
    NextPage,
    ScrollingGroup,
    StubScroll,
    sync_scroll,
)
from vkbottle_dialog.widgets.text import Const


class SG(StatesGroup):
    a = State()


def buttons(n):
    return [Button(Const(str(i)), id=f"b{i}") for i in range(n)]


async def test_scrolling_group_pages(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    sg = ScrollingGroup(*buttons(5), id="sc", height=2, width=1)
    kb = await sg.render_keyboard({}, m)
    # страница 0: 2 строки контента + пейджер
    assert [b.label for b in kb[0]] == ["0"] and [b.label for b in kb[1]] == ["1"]
    pager = kb[-1]
    assert [b.callback_data for b in pager] == [
        "sc:0",
        "sc:0",
        "sc:0",
        "sc:1",
        "sc:2",
    ]  # «, ‹ на 1-й странице клампятся в 0; текущая — no-op

    await sg.process_callback("sc:2", m)
    kb = await sg.render_keyboard({}, m)
    assert [b.label for b in kb[0]] == ["4"]  # последняя страница


async def test_page_clamped(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    sg = ScrollingGroup(*buttons(3), id="sc", height=2, width=1)
    await sg.process_callback("sc:99", m)
    assert sg.get_page(m) == 1  # максимум — последняя страница


async def test_external_pager_and_stub(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    stub = StubScroll(id="st", pages="pages")
    m.find_scroll = lambda sid: {"st": stub}[sid]
    pager = NextPage(scroll_id="st", id="np")
    data = {"pages": 3}
    m._data = data
    kb = await pager.render_keyboard(data, m)
    assert kb[0][0].callback_data == "np:1"
    await pager.process_callback("np:1", m)
    assert stub.get_page(m) == 1


async def test_sync_scroll(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    a = StubScroll(id="a", pages="p")
    b = StubScroll(id="b", pages="p")
    m.find_scroll = lambda sid: {"a": a, "b": b}[sid]
    handler = sync_scroll("a", "b")
    await handler(None, a, m, 2)
    assert b.get_page(m) == 2


async def test_sync_scroll_bidirectional_does_not_recurse_infinitely(fake_manager_factory):
    # Регрессия на FIX 3: set_page теперь сам зовёт on_page_changed (раньше
    # sync_scroll писало widget_data напрямую, колбэк вообще не срабатывал) —
    # наивная взаимная синхронизация (a зеркалит на b, b зеркалит на a) без
    # guard'а на "страница уже такая" рекурсировала бы бесконечно
    # (RecursionError). get_page(manager) != page в sync_scroll делает
    # зеркальный хоп no-op'ом, как только у цели уже нужная страница (а у a
    # она уже выставлена до срабатывания его собственного колбэка) —
    # рекурсия конечна: a.set_page -> b.set_page -> (a уже на этой странице,
    # стоп).
    m = fake_manager_factory(SG.a)
    a = StubScroll(id="a", pages="p", on_page_changed=sync_scroll("b"))
    b = StubScroll(id="b", pages="p", on_page_changed=sync_scroll("a"))
    m.find_scroll = lambda sid: {"a": a, "b": b}[sid]

    await a.set_page(m, 3)  # не должно упасть RecursionError

    assert a.get_page(m) == 3
    assert b.get_page(m) == 3


async def test_sync_scroll_targeting_list_group_does_not_corrupt_row_state(fake_manager_factory):
    # FIX 3: sync_scroll раньше писало widget_data[sid] = int(page) напрямую,
    # затирая dict строк ListGroup'а ({item_id: {...}}) целым числом — следующий
    # get_page ListGroup'а падал AttributeError (.setdefault на int), а
    # состояние отмеченных строк терялось безвозвратно. Через target.set_page
    # (переопределённый ListGroup'ом) страница живёт отдельно от строк.
    m = fake_manager_factory(SG.a)
    lg = ListGroup(
        Checkbox(Const("[x]"), Const("[ ]"), id="chk"),
        id="lg",
        item_id_getter=lambda item: item["id"],
        items="items",
        page_size=1,
    )
    items = [{"id": "1"}, {"id": "2"}]
    await lg.render_keyboard({"items": items}, m)  # прогреваем widget_data строк
    await lg.process_callback("lg:1:chk", m)  # чекбокс строки "1" отмечен
    assert m.current_context().widget_data["lg"]["1"]["chk"] is True

    src = StubScroll(id="src", pages="p")
    m.find_scroll = lambda sid: {"src": src, "lg": lg}[sid]
    handler = sync_scroll("src", "lg")
    await handler(None, src, m, 1)  # синхронизируем страницу "lg" на 1

    # страница сдвинулась через set_page (не корраптит dict строк)
    assert lg.get_page(m) == 1
    # состояние отмеченной строки "1" пережило синхронизацию
    assert m.current_context().widget_data["lg"]["1"]["chk"] is True
    # рендер после синхронизации не падает (регрессия: int(dict) TypeError)
    kb = await lg.render_keyboard({"items": items}, m)
    assert kb  # страница 1 отрендерилась (не упала)


async def test_malformed_scrolling_group_callback(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    sg = ScrollingGroup(*buttons(5), id="sc", height=2, width=1)
    result = await sg.process_callback("sc:abc", m)
    assert result is False  # malformed item not handled


async def test_stub_scroll_clamps_page(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    stub = StubScroll(id="st", pages="pages")
    m._data = {"pages": 3}
    await stub.process_callback("st:99", m)
    assert stub.get_page(m) == 2  # clamped to pages-1


async def test_pager_raises_on_missing_scroll_id(fake_manager_factory):
    # M8: пейджер, ссылающийся на несуществующий scroll_id (опечатка/окно
    # без соответствующего ScrollingGroup/StubScroll), раньше падал глубже
    # с невнятным AttributeError на None — теперь явная DialogConfigError
    # с именем виджета и scroll_id.
    m = fake_manager_factory(SG.a)
    m.find_scroll = lambda sid: None
    pager = NextPage(scroll_id="missing", id="np")
    with pytest.raises(DialogConfigError, match="missing"):
        await pager.render_keyboard({}, m)
