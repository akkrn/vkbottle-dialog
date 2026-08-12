"""Работа в беседе: у каждого участника — свой независимый стек диалога.

Стек хранится по ключу (group_id, peer_id, owner_id). Для сообщений из
беседы (peer_id >= 2_000_000_000) owner_id — это from_id отправителя, а не
peer_id беседы. Поэтому если участники A и Б пишут /counter в одну и ту же
беседу, они получают ДВА независимых счётчика: клик участника A по кнопке
двигает только его диалог и его окно, диалог участника Б не затрагивается —
даже если оба сообщения-окна лежат в одном и том же чате.

Запуск: VK_TOKEN=<токен группы> python examples/chat.py
Бот должен быть добавлен в беседу с правом чтения сообщений.
"""

import os

from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage
from vkbottle_dialog.widgets.kbd import Button, Cancel
from vkbottle_dialog.widgets.text import Const, Format


class ChatSG(StatesGroup):
    counter = State()


async def on_increment(event, widget, manager):
    # Изменения видит только владелец этого стека — окно другого участника
    # беседы (если он тоже запустил /counter) перерисуется отдельно, своим
    # собственным кликом.
    manager.dialog_data["count"] = manager.dialog_data.get("count", 0) + 1


async def counter_getter(dialog_manager, **kwargs):
    return {"count": dialog_manager.dialog_data.get("count", 0)}


dialog = Dialog(
    Window(
        Format("Ваш личный счётчик в этой беседе: {count}"),
        Button(Const("+1"), id="inc", on_click=on_increment),
        Cancel(),
        state=ChatSG.counter,
        getter=counter_getter,
    ),
)

bot = Bot(os.environ["VK_TOKEN"])
setup_dialogs(bot, dialog, storage=MemoryStorage())


@bot.on.message(NotInDialog(), text="/counter")
async def start_counter(message, dialog_manager):
    await dialog_manager.start(ChatSG.counter, mode=StartMode.RESET_STACK)


if __name__ == "__main__":
    bot.run_forever()
