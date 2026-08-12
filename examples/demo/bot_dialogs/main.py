"""Главное меню демо-бота: витрина секций vkbottle-dialog.

Задача 1: секций ещё нет, меню содержит только ссылку на репозиторий.
Каждая следующая задача (2-6) добавляет Start-кнопку своей секции сюда
и свой диалог в bot_dialogs/__init__.py:ALL_DIALOGS."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.api.entities import LaunchMode
from vkbottle_dialog.widgets.kbd import Group, Url
from vkbottle_dialog.widgets.text import Const

from .states import Main

main_dialog = Dialog(
    Window(
        Const("vkbottle-dialog: витрина виджетов"),
        Const("Выберите секцию:"),
        Group(
            Url(Const("📖 О библиотеке"), Const("https://github.com/akkrn/vkbottle-dialog")),
            width=2,
        ),
        state=Main.MAIN,
    ),
    launch_mode=LaunchMode.ROOT,
)
