"""Главное меню демо-бота: витрина секций vkbottle-dialog.

Каждая секция — своя Start-кнопка здесь и свой диалог в
bot_dialogs/__init__.py:ALL_DIALOGS."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.api.entities import LaunchMode
from vkbottle_dialog.widgets.kbd import ScrollingGroup, Start, Url
from vkbottle_dialog.widgets.text import Const

from .states import (
    AccessDemo,
    CalendarSG,
    CarouselDemo,
    CounterSG,
    Layouts,
    ListDemo,
    Main,
    Multiwidget,
    Scrolls,
    Selects,
    Switch,
    TextKb,
    VkFeatures,
)

# >10 секций не влезает в лимит инлайн-клавиатуры (спека §2) — меню на
# ScrollingGroup(height=5, width=1): 5 кнопок/страница + строка пейджера
# (5 кнопок) = 10 кнопок/6 строк на страницу, ровно бюджет. 13 виджетов
# (12 Start + Url) -> 3 страницы; «📋 ListGroup» уже на 2-й странице,
# «🎠 Карусель»/«🔒 Доступ» — на 3-й (walk-тест обходит их через пейджер).
main_dialog = Dialog(
    Window(
        Const("vkbottle-dialog: витрина виджетов"),
        Const("Выберите секцию:"),
        ScrollingGroup(
            Start(Const("📐 Лейауты"), id="to_layouts", state=Layouts.MAIN),
            Start(Const("📜 Скроллы"), id="to_scrolls", state=Scrolls.MAIN),
            Start(Const("☑️ Селекты"), id="to_selects", state=Selects.MAIN),
            Start(Const("📅 Календарь"), id="to_calendar", state=CalendarSG.MAIN),
            Start(Const("💯 Счётчик"), id="to_counter", state=CounterSG.MAIN),
            Start(Const("🎛 Мультивиджет"), id="to_multiwidget", state=Multiwidget.MAIN),
            Start(Const("🔢 Мастер"), id="to_switch", state=Switch.MAIN),
            Start(Const("⌨️ Нижняя клавиатура (ЛС)"), id="to_text_kb", state=TextKb.MAIN),
            Start(Const("✨ VK-фишки"), id="to_vk_features", state=VkFeatures.MAIN),
            Start(Const("📋 ListGroup"), id="to_list", state=ListDemo.MAIN),
            Start(Const("🎠 Карусель"), id="to_carousel", state=CarouselDemo.MAIN),
            Start(Const("🔒 Доступ"), id="to_access", state=AccessDemo.MAIN),
            Url(Const("📖 О библиотеке"), Const("https://github.com/akkrn/vkbottle-dialog")),
            id="menu_sg",
            height=5,
            width=1,
        ),
        state=Main.MAIN,
    ),
    launch_mode=LaunchMode.ROOT,
)
