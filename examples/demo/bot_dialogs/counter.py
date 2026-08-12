"""Секция «Счётчик»: Counter (кнопки +/-, клик по значению шлёт снекбар) и
текстовый Progress, синхронизированный с текущим значением счётчика."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Counter
from vkbottle_dialog.widgets.text import Const, Progress

from .common import nav_row
from .states import CounterSG


async def on_text_click(event, managed, manager) -> None:
    await manager.answer(snackbar=f"Значение: {managed.get_value():g}")


def counter_getter(dialog_manager, **kwargs) -> dict:
    return {"progress": dialog_manager.find("cnt").get_value() / 10 * 100}


counter_dialog = Dialog(
    Window(
        Const("💯 Счётчик: Counter + Progress"),
        Const("Кнопки −/+ меняют значение (0..10), клик по числу — снекбар."),
        Counter(id="cnt", max_value=10, on_text_click=on_text_click),
        Progress(field="progress", width=10),
        nav_row(CounterSG.MAIN),
        state=CounterSG.MAIN,
        getter=counter_getter,
    ),
)
