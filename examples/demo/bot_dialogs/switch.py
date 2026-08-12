"""Секция «Мастер»: Switch/Next/Back мастер из 3 шагов с итоговым резюме.

Демонстрирует навигацию между окнами мастера и использование Case для
условного отображения результатов выбора."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Back, Checkbox, Next, Radio, Row
from vkbottle_dialog.widgets.text import Case, Const, Format

from .common import nav_row
from .states import Switch


def switch_getter(dialog_manager, **kwargs) -> dict:
    """Собирает данные из виджетов INPUT окна для отображения в LAST."""
    return {
        "option": dialog_manager.find("sw_chk").is_checked(),
        "emoji": dialog_manager.find("sw_emo").get_checked() or "—",
    }


switch_dialog = Dialog(
    Window(
        Const("🔢 Мастер из 3 шагов"),
        Const("Это окно 1 из 3. Введите данные в следующих окнах."),
        Next(),
        nav_row(Switch.MAIN),
        state=Switch.MAIN,
    ),
    Window(
        Const("🔢 Мастер из 3 шагов"),
        Const("Окно 2 из 3: выберите опцию и эмодзи."),
        Checkbox(
            Const("✓ Опция включена"),
            Const("Опция выключена"),
            id="sw_chk",
        ),
        Radio(
            Format("🔘 {item}"),
            Format("⚪ {item}"),
            id="sw_emo",
            item_id_getter=str,
            items=["😆", "😱", "🤖"],
        ),
        Row(Back(id="sw_back_input"), Next()),
        nav_row(Switch.MAIN),
        state=Switch.INPUT,
    ),
    Window(
        Const("🔢 Мастер из 3 шагов"),
        Const("Окно 3 из 3: итоговое резюме."),
        Case(
            {
                True: Const("Опция: включена"),
                False: Const("Опция: выключена"),
            },
            selector="option",
        ),
        Format("Эмодзи: {emoji}"),
        Back(id="sw_back_last"),
        nav_row(Switch.MAIN),
        state=Switch.LAST,
        getter=switch_getter,
    ),
)
