"""Секция «Нижняя клавиатура»: единственное окно рендерится через
TextKeyboardFactory — обычная (не инлайн) reply-клавиатура VK. Работает
только в личных сообщениях: в беседе такая клавиатура общая на весь чат,
поэтому TextKeyboardFactory поднимает DialogConfigError (см. window.py) —
секция помечена «(ЛС)» и в тексте окна, и в главном меню."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Button, Column
from vkbottle_dialog.widgets.markup import TextKeyboardFactory
from vkbottle_dialog.widgets.text import Const, Format

from .common import nav_row
from .states import TextKb

# снекбары работают только на inline (message_event); для текстовой
# клавиатуры (message_new, event_id отсутствует) — эхо выбора в тексте окна
_CHOICES = {
    "tk_pizza": "Пицца",
    "tk_burger": "Бургер",
    "tk_sushi": "Суши",
    "tk_salad": "Салат",
}


async def on_pick(event, widget, manager) -> None:
    manager.dialog_data["picked"] = _CHOICES[widget.widget_id]


def text_kb_getter(dialog_manager, **kwargs) -> dict:
    return {"picked": dialog_manager.dialog_data.get("picked")}


text_kb_dialog = Dialog(
    Window(
        Const("⌨️ Нижняя клавиатура VK (ЛС)"),
        Const(
            "Это reply-клавиатура (TextKeyboardFactory), а не инлайн. "
            "В беседе такое окно упадёт с DialogConfigError — общая "
            "клавиатура на весь чат, только для ЛС."
        ),
        Format("Вы выбрали: {picked}", when="picked"),
        Column(
            Button(Const("🍕 Пицца"), id="tk_pizza", on_click=on_pick),
            Button(Const("🍔 Бургер"), id="tk_burger", on_click=on_pick),
            Button(Const("🍣 Суши"), id="tk_sushi", on_click=on_pick),
            Button(Const("🥗 Салат"), id="tk_salad", on_click=on_pick),
        ),
        nav_row(),
        state=TextKb.MAIN,
        markup_factory=TextKeyboardFactory(),
        getter=text_kb_getter,
    ),
)
