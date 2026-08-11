from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import (
    Button,
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
        "sc:0", "sc:0", "sc:0", "sc:1", "sc:2",
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
