"""Секция «Лейауты»: Row/Column/Group на одних и тех же виджетах SELECT+BUTTON
показывают, как ширина влияет на раскладку кнопок в клавиатуре."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Button, Column, Group, Row, Select, SwitchTo
from vkbottle_dialog.widgets.text import Const, Format

from .common import MAIN_MENU_BUTTON, nav_row
from .states import Layouts

FRUITS = ["Яблоко", "Банан", "Апельсин", "Груша"]


async def on_fruit_click(event, widget, manager, item_id) -> None:
    await manager.answer(snackbar=f"Выбрано: {item_id}")


SELECT = Select(
    Format("{item}"),
    id="fr",
    item_id_getter=str,
    items=FRUITS,
    on_click=on_fruit_click,
)
BUTTON = Button(Const("Кнопка"), id="btn", snackbar="Клик!")

layouts_dialog = Dialog(
    Window(
        Const("📐 Лейауты: Row / Column / Group"),
        Const("Одни и те же кнопки (4 фрукта + «Кнопка»), разная раскладка:"),
        Group(
            SwitchTo(Const("Row"), id="to_row", state=Layouts.ROW),
            SwitchTo(Const("Column"), id="to_column", state=Layouts.COLUMN),
            SwitchTo(Const("Group"), id="to_group", state=Layouts.GROUP),
            MAIN_MENU_BUTTON,
            width=2,
        ),
        state=Layouts.MAIN,
    ),
    Window(
        Const("Row — все кнопки вытянуты в одну строку."),
        Row(SELECT, BUTTON),
        nav_row(Layouts.MAIN),
        state=Layouts.ROW,
    ),
    Window(
        Const("Column — каждая кнопка на своей строке."),
        Column(SELECT, BUTTON),
        nav_row(Layouts.MAIN),
        state=Layouts.COLUMN,
    ),
    Window(
        Const("Group(width=2) — кнопки идут по 2 в строке."),
        Group(SELECT, BUTTON, width=2),
        nav_row(Layouts.MAIN),
        state=Layouts.GROUP,
    ),
)
