"""Секция «Скроллы»: ScrollingGroup/NumberedPager/List/ScrollingText/
StubScroll/sync_scroll на общем списке товаров и на длинном тексте
показывают все способы постранично листать клавиатуру и текст."""

from pathlib import Path

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import (
    Button,
    CurrentPage,
    Group,
    NextPage,
    NumberedPager,
    PrevPage,
    Row,
    ScrollingGroup,
    StubScroll,
    SwitchTo,
    sync_scroll,
)
from vkbottle_dialog.widgets.media import StaticMedia
from vkbottle_dialog.widgets.text import Const, Format, List, ScrollingText

from .common import MAIN_MENU_BUTTON, nav_row
from .states import Scrolls

MEDIA_DIR = Path(__file__).parent.parent / "media"

PRODUCTS = [f"Товар {i}" for i in range(1, 13)]
PRODUCTS_PAGERS = PRODUCTS[:8]

LONG_TEXT = (
    "ScrollingText режет длинный текст на страницы фиксированной длины в "
    "символах — никакого понимания слов или абзацев, просто плоский срез "
    "строки. Это самый простой способ показать пользователю текст, который "
    "не влезает в одно сообщение: инструкцию, описание товара, длинный "
    "отзыв или список правил. Управляют перелистыванием PrevPage, "
    "CurrentPage и NextPage — те же виджеты, что и у ScrollingGroup, потому "
    "что оба используют общий протокол BaseScroll: get_page_count и "
    "set_page. Благодаря этому один и тот же набор кнопок пагинации "
    "работает и с клавиатурой, и с текстом, и со StubScroll, у которого "
    "вообще нет собственных данных — только число страниц."
)


async def products_getter(**kwargs) -> dict:
    return {"products": PRODUCTS}


def stub_getter(dialog_manager, **kwargs) -> dict:
    page = dialog_manager.find_scroll("stub").get_page(dialog_manager)
    return {"stub_pages": 7, "current_page1": page + 1}


MAIN_WINDOW = Window(
    Const("📜 Скроллы: пагинация клавиатур и текста"),
    Const("Выберите подсекцию:"),
    Group(
        SwitchTo(Const("По умолчанию"), id="to_default", state=Scrolls.DEFAULT),
        SwitchTo(Const("Пейджер"), id="to_pagers", state=Scrolls.PAGERS),
        SwitchTo(Const("Список"), id="to_list", state=Scrolls.LIST),
        SwitchTo(Const("Текст"), id="to_text", state=Scrolls.TEXT),
        SwitchTo(Const("Заглушка"), id="to_stub", state=Scrolls.STUB),
        SwitchTo(Const("Синхронизация"), id="to_sync", state=Scrolls.SYNC),
        MAIN_MENU_BUTTON,
        width=2,
    ),
    state=Scrolls.MAIN,
)

DEFAULT_WINDOW = Window(
    Const("ScrollingGroup — список кнопок бьётся на страницы, пейджер добавляется сам."),
    ScrollingGroup(
        *(Button(Const(name), id=f"p{i}", snackbar=name) for i, name in enumerate(PRODUCTS, 1)),
        id="sg",
        height=3,
        width=1,
    ),
    nav_row(Scrolls.MAIN),
    state=Scrolls.DEFAULT,
)

PAGERS_WINDOW = Window(
    Const("NumberedPager — пронумерованные кнопки страниц (встроенный пейджер спрятан)."),
    ScrollingGroup(
        *(
            Button(Const(name), id=f"pg{i}", snackbar=name)
            for i, name in enumerate(PRODUCTS_PAGERS, 1)
        ),
        id="sgh",
        height=2,
        width=1,
        hide_pager=True,
    ),
    NumberedPager(scroll_id="sgh"),
    nav_row(Scrolls.MAIN),
    state=Scrolls.PAGERS,
)

LIST_WINDOW = Window(
    Const("List — текстовый список с постраничной пагинацией."),
    List(Format("{pos}. {item}"), items="products", id="ls", page_size=4),
    NumberedPager(scroll_id="ls"),
    nav_row(Scrolls.MAIN),
    state=Scrolls.LIST,
    getter=products_getter,
)

TEXT_WINDOW = Window(
    ScrollingText(Const(LONG_TEXT), id="st", page_size=400),
    Row(PrevPage(scroll_id="st"), CurrentPage(scroll_id="st"), NextPage(scroll_id="st")),
    nav_row(Scrolls.MAIN),
    state=Scrolls.TEXT,
)

STUB_WINDOW = Window(
    Format("Страница {current_page1}/7"),
    StaticMedia(path=Format(str(MEDIA_DIR / "{current_page1}.png"))),
    StubScroll(id="stub", pages="stub_pages"),
    Row(PrevPage(scroll_id="stub"), NextPage(scroll_id="stub")),
    nav_row(Scrolls.MAIN),
    state=Scrolls.STUB,
    getter=stub_getter,
)

SYNC_WINDOW = Window(
    Const("sync_scroll — клавиатура и текстовый список листаются синхронно."),
    ScrollingGroup(
        *(Button(Const(name), id=f"sy{i}", snackbar=name) for i, name in enumerate(PRODUCTS, 1)),
        id="sync_kbd",
        height=3,
        width=1,
        on_page_changed=sync_scroll("sync_list"),
    ),
    List(Format("{pos}. {item}"), items="products", id="sync_list", page_size=3),
    nav_row(Scrolls.MAIN),
    state=Scrolls.SYNC,
    getter=products_getter,
)

scrolls_dialog = Dialog(
    MAIN_WINDOW,
    DEFAULT_WINDOW,
    PAGERS_WINDOW,
    LIST_WINDOW,
    TEXT_WINDOW,
    STUB_WINDOW,
    SYNC_WINDOW,
)
