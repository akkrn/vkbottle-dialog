"""Секция «Мультивиджет»: Checkbox + Radio + Counter в одном окне.

Демонстрирует комбинирование разных типов виджетов выбора. Multiselect исключён
из-за бюджета клавиатуры (лимит 10 кнопок, 6 строк)."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Checkbox, Counter, Radio
from vkbottle_dialog.widgets.text import Const, Format

from .common import nav_row
from .states import Multiwidget

multiwidget_dialog = Dialog(
    Window(
        Const("🎛 Мультивиджет: Checkbox + Radio + Counter"),
        Const(
            "В одном окне несколько типов виджетов выбора. "
            "Multiselect исключён: не влезает в бюджет 10 кнопок."
        ),
        Checkbox(
            Const("✓ Опция"),
            Const("Опция"),
            id="mw_chk",
        ),
        Radio(
            Format("🔘 {item}"),
            Format("⚪ {item}"),
            id="mw_emo",
            item_id_getter=str,
            items=["😆", "😱", "🤖"],
        ),
        Counter(id="mw_cnt", max_value=5),
        nav_row(Multiwidget.MAIN),
        state=Multiwidget.MAIN,
    ),
)
