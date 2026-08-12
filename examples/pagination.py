"""Пагинация: 30 элементов из геттера, отображаемые через ScrollingGroup + Select.

ScrollingGroup сам режет список на страницы (height — строк на странице) и
дорисовывает строку-пейджер («« ‹ N/M › »»), когда страниц больше одной.

Запуск: VK_TOKEN=<токен группы> python examples/pagination.py
"""

import os

from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage
from vkbottle_dialog.widgets.kbd import ScrollingGroup, Select
from vkbottle_dialog.widgets.text import Const, Format


class CatalogSG(StatesGroup):
    items = State()


async def items_getter(**kwargs):
    return {"items": [{"id": i, "title": f"Товар №{i}"} for i in range(1, 31)]}


async def on_item_click(event, widget, manager, item_id):
    # message_event — snackbar доступен, в отличие от обычного сообщения
    await manager.answer(snackbar=f"Выбран товар #{item_id}")


dialog = Dialog(
    Window(
        Const("Каталог (30 позиций, постранично):"),
        ScrollingGroup(
            Select(
                Format("{item[title]}"),
                id="select_item",
                item_id_getter=lambda item: item["id"],
                items="items",
                on_click=on_item_click,
            ),
            id="scroll",
            height=5,
        ),
        state=CatalogSG.items,
        getter=items_getter,
    ),
)

bot = Bot(os.environ["VK_TOKEN"])
setup_dialogs(bot, dialog, storage=MemoryStorage())


@bot.on.message(NotInDialog(), text="/catalog")
async def start_catalog(message, dialog_manager):
    await dialog_manager.start(CatalogSG.items, mode=StartMode.RESET_STACK)


if __name__ == "__main__":
    bot.run_forever()
