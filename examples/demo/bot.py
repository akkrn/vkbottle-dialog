"""Демо-бот vkbottle-dialog: витрина всех виджетов.

Запуск: VK_TOKEN=<токен группы> python -m examples.demo.bot
Группе нужны Long Poll API и событие message_event.
"""

from __future__ import annotations

import logging
import os

from vkbottle import Bot

from vkbottle_dialog import DialogManager, StartMode, setup_dialogs
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage

from .bot_dialogs import ALL_DIALOGS
from .bot_dialogs.states import Main


async def on_unknown_intent(event, dialog_manager: DialogManager) -> None:
    await dialog_manager.start(Main.MAIN, mode=StartMode.RESET_STACK)


def build_bot(token: str) -> Bot:
    bot = Bot(token)
    setup_dialogs(
        bot,
        *ALL_DIALOGS,
        storage=MemoryStorage(),
        on_unknown_intent=on_unknown_intent,
    )

    @bot.on.message(NotInDialog())
    async def any_text(message, dialog_manager: DialogManager) -> None:
        await dialog_manager.start(Main.MAIN, mode=StartMode.RESET_STACK)

    return bot


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = build_bot(os.environ["VK_TOKEN"])
    bot.run_forever()


if __name__ == "__main__":
    main()
