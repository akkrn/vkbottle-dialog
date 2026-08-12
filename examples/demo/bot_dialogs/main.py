"""Главное меню демо-бота: витрина секций vkbottle-dialog.

Задача 1: секций ещё нет, меню содержит только ссылку на репозиторий.
Каждая следующая задача (2-6) добавляет Start-кнопку своей секции сюда
и свой диалог в bot_dialogs/__init__.py:ALL_DIALOGS."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.api.entities import LaunchMode
from vkbottle_dialog.widgets.kbd import Group, Start, Url
from vkbottle_dialog.widgets.text import Const

from .states import CalendarSG, CounterSG, Layouts, Main, Multiwidget, Scrolls, Selects, Switch

main_dialog = Dialog(
    Window(
        Const("vkbottle-dialog: витрина виджетов"),
        Const("Выберите секцию:"),
        Group(
            Start(Const("📐 Лейауты"), id="to_layouts", state=Layouts.MAIN),
            Start(Const("📜 Скроллы"), id="to_scrolls", state=Scrolls.MAIN),
            Start(Const("☑️ Селекты"), id="to_selects", state=Selects.MAIN),
            Start(Const("📅 Календарь"), id="to_calendar", state=CalendarSG.MAIN),
            Start(Const("💯 Счётчик"), id="to_counter", state=CounterSG.MAIN),
            Start(Const("🎛 Мультивиджет"), id="to_multiwidget", state=Multiwidget.MAIN),
            Start(Const("🔢 Мастер"), id="to_switch", state=Switch.MAIN),
            Url(Const("📖 О библиотеке"), Const("https://github.com/akkrn/vkbottle-dialog")),
            width=2,
        ),
        state=Main.MAIN,
    ),
    launch_mode=LaunchMode.ROOT,
)
