"""Секция «Нижняя клавиатура»: единственное окно рендерится через
TextKeyboardFactory — обычная (не инлайн) reply-клавиатура VK. Работает
только в личных сообщениях: в беседе такая клавиатура общая на весь чат,
поэтому TextKeyboardFactory поднимает DialogConfigError (см. window.py) —
секция помечена «(ЛС)» и в тексте окна, и в главном меню."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Button, Column
from vkbottle_dialog.widgets.markup import TextKeyboardFactory
from vkbottle_dialog.widgets.text import Const

from .common import nav_row
from .states import TextKb

text_kb_dialog = Dialog(
    Window(
        Const("⌨️ Нижняя клавиатура VK (ЛС)"),
        Const(
            "Это reply-клавиатура (TextKeyboardFactory), а не инлайн. "
            "В беседе такое окно упадёт с DialogConfigError — общая "
            "клавиатура на весь чат, только для ЛС."
        ),
        Column(
            Button(Const("🍕 Пицца"), id="tk_pizza", snackbar="Выбрано: Пицца"),
            Button(Const("🍔 Бургер"), id="tk_burger", snackbar="Выбрано: Бургер"),
            Button(Const("🍣 Суши"), id="tk_sushi", snackbar="Выбрано: Суши"),
            Button(Const("🥗 Салат"), id="tk_salad", snackbar="Выбрано: Салат"),
        ),
        nav_row(TextKb.MAIN),
        state=TextKb.MAIN,
        markup_factory=TextKeyboardFactory(),
    ),
)
