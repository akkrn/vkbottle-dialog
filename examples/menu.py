"""Минимальный пример: главное меню с переходом на второй экран и Cancel.

Запуск: VK_TOKEN=<токен группы> python examples/menu.py
Группа должна иметь включённый Long Poll API и событие message_event
(см. README, раздел «Обязательно»).
"""

import os

from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage
from vkbottle_dialog.widgets.kbd import Cancel, SwitchTo
from vkbottle_dialog.widgets.text import Const


class MenuSG(StatesGroup):
    main = State()
    info = State()


dialog = Dialog(
    Window(
        Const("Главное меню. Выберите пункт:"),
        SwitchTo(Const("О боте"), id="to_info", state=MenuSG.info),
        Cancel(Const("Закрыть")),
        state=MenuSG.main,
    ),
    Window(
        Const("Это демонстрационный бот на vkbottle-dialog."),
        SwitchTo(Const("Назад"), id="to_main", state=MenuSG.main),
        state=MenuSG.info,
    ),
)

bot = Bot(os.environ["VK_TOKEN"])
setup_dialogs(bot, dialog, storage=MemoryStorage())


@bot.on.message(NotInDialog(), text="/start")
async def start(message, dialog_manager):
    # NotInDialog(): хендлер сработает, только если у пользователя ещё нет
    # активного диалога — иначе повторный /start не пересоздаст меню поверх
    # уже открытого окна (см. README, «Обязательно»).
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


if __name__ == "__main__":
    bot.run_forever()
