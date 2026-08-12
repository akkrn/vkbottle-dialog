import pytest

from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.text import Const, Format, List, ScrollingText


class SG(StatesGroup):
    a = State()


ITEMS = [f"i{n}" for n in range(7)]


async def test_list_without_paging_unchanged(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    lst = List(Format("{pos}. {item}"), items=ITEMS)
    out = await lst.render_text({}, m)
    assert out.startswith("1. i0") and out.endswith("7. i6")


def test_page_size_requires_id():
    with pytest.raises(DialogConfigError):
        List(Format("{item}"), items=ITEMS, page_size=3)


async def test_list_paged_absolute_pos_and_context(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    lst = List(Format("{pos}. {item} p{current_page1}/{pages}"), items=ITEMS, id="ls", page_size=3)
    assert await lst.get_page_count({}, m) == 3
    await lst.set_page(m, 2)
    out = await lst.render_text({}, m)
    assert out == "7. i6 p3/3"  # абсолютный pos, ключи страницы


async def test_list_empty_zero_pages(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    lst = List(Format("{item}"), items=[], id="ls", page_size=3)
    assert await lst.get_page_count({}, m) == 0
    assert await lst.render_text({}, m) == ""


async def test_scrolling_text_flat_slice(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    st = ScrollingText(Const("abcdefghij"), id="st", page_size=4)
    assert await st.get_page_count({}, m) == 3  # 4+4+2
    assert await st.render_text({}, m) == "abcd"
    await st.set_page(m, 2)
    assert await st.render_text({}, m) == "ij"


async def test_scrolling_text_empty(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    st = ScrollingText(Const(""), id="st", page_size=4)
    assert await st.get_page_count({}, m) == 0


def test_paged_list_found_by_window_find_scroll():
    from vkbottle_dialog.window import Window

    lst = List(Format("{item}"), items=["a", "b"], id="ls", page_size=1)
    win = Window(lst, state=SG.a)
    assert win.find_scroll("ls") is lst
    st = ScrollingText(Const("abcdef"), id="st", page_size=2)
    win2 = Window(st, state=SG.a)
    assert win2.find_scroll("st") is st
