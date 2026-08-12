"""Анкета: два окна TextInput (имя, возраст) и финальное окно с результатом.

Показывает валидацию ввода через TextInput(type_factory=..., on_error=...).
У message-события (в отличие от message_event) нет snackbar — поэтому
ошибку ввода показываем прямо в тексте окна: on_error кладёт сообщение в
dialog_data["error"], а Const(..., when="error") рисует его, только пока
ошибка не сброшена.

Запуск: VK_TOKEN=<токен группы> python examples/survey.py
"""

import os

from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage
from vkbottle_dialog.widgets.input import TextInput
from vkbottle_dialog.widgets.kbd import Back
from vkbottle_dialog.widgets.text import Const, Format


class SurveySG(StatesGroup):
    name = State()
    age = State()
    done = State()


async def on_name_entered(message, widget, manager, value):
    manager.dialog_data["name"] = value
    await manager.next()


async def on_age_entered(message, widget, manager, value):
    manager.dialog_data["age"] = value
    manager.dialog_data.pop("error", None)
    await manager.next()


async def on_age_error(message, widget, manager, error):
    manager.dialog_data["error"] = "Введите возраст числом, например: 25"


async def age_getter(dialog_manager, **kwargs):
    # Достаём ошибку из dialog_data на верхний уровень данных окна —
    # только там её видит when="error" и текстовые виджеты.
    return {"error": dialog_manager.dialog_data.get("error")}


async def result_getter(dialog_manager, **kwargs):
    return dialog_manager.dialog_data


dialog = Dialog(
    Window(
        Const("Как вас зовут?"),
        TextInput(id="name", on_success=on_name_entered),
        state=SurveySG.name,
    ),
    Window(
        Const("Сколько вам лет? Введите число."),
        Const("⚠ Возраст должен быть числом, например: 25", when="error"),
        TextInput(id="age", type_factory=int, on_success=on_age_entered,
                  on_error=on_age_error),
        Back(),
        state=SurveySG.age,
        getter=age_getter,
    ),
    Window(
        Format("Готово! {name}, вам {age} лет."),
        state=SurveySG.done,
        getter=result_getter,
    ),
)

bot = Bot(os.environ["VK_TOKEN"])
setup_dialogs(bot, dialog, storage=MemoryStorage())


@bot.on.message(NotInDialog(), text="/survey")
async def start_survey(message, dialog_manager):
    await dialog_manager.start(SurveySG.name, mode=StartMode.RESET_STACK)


if __name__ == "__main__":
    bot.run_forever()
