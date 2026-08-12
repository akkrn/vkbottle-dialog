"""Общие для всех секций демо кнопки навигации."""

from vkbottle_dialog.fsm import State
from vkbottle_dialog.widgets.kbd import Row, Start, SwitchTo
from vkbottle_dialog.widgets.text import Const

from .states import Main

MAIN_MENU_BUTTON = Start(Const("☰ Главное меню"), id="__main__", state=Main.MAIN)


def nav_row(back_to: State | None = None) -> Row:
    if back_to is None:
        return Row(MAIN_MENU_BUTTON)
    return Row(SwitchTo(Const("◀ Назад"), id="__back__", state=back_to), MAIN_MENU_BUTTON)
