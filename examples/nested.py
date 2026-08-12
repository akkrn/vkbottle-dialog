"""Вложенный диалог: родитель открывает дочерний через Start(),
а результат забирает через Dialog(on_process_result=...).

Дочерний диалог завершается вызовом manager.done(result=...) — значение
result долетает до родителя в on_process_result(start_data, result, manager).

Запуск: VK_TOKEN=<токен группы> python examples/nested.py
"""

import os

from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage
from vkbottle_dialog.widgets.kbd import Button, Cancel, Start
from vkbottle_dialog.widgets.text import Const, Format


class MenuSG(StatesGroup):
    main = State()


class ConfirmSG(StatesGroup):
    ask = State()


async def on_confirm_result(start_data, result, manager):
    manager.dialog_data["last_result"] = "да" if result else "нет"


async def menu_getter(dialog_manager, **kwargs):
    return {"last_result": dialog_manager.dialog_data.get("last_result", "—")}


async def on_yes(event, widget, manager):
    await manager.done(result=True)


async def on_no(event, widget, manager):
    await manager.done(result=False)


menu_dialog = Dialog(
    Window(
        Format("Главное меню. Последний ответ на вопрос: {last_result}"),
        Start(Const("Задать вопрос"), id="ask", state=ConfirmSG.ask),
        state=MenuSG.main,
        getter=menu_getter,
    ),
    on_process_result=on_confirm_result,
)

confirm_dialog = Dialog(
    Window(
        Const("Подтвердить действие?"),
        Button(Const("Да"), id="yes", on_click=on_yes),
        Button(Const("Нет"), id="no", on_click=on_no),
        Cancel(Const("Отмена")),
        state=ConfirmSG.ask,
    ),
)

bot = Bot(os.environ["VK_TOKEN"])
setup_dialogs(bot, menu_dialog, confirm_dialog, storage=MemoryStorage())


@bot.on.message(NotInDialog(), text="/start")
async def start(message, dialog_manager):
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


if __name__ == "__main__":
    bot.run_forever()
