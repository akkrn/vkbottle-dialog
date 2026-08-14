"""Секция «ListGroup»: строки (Checkbox «выбрать»+item.name и Button
«удалить»), состояние изолировано per-row через SubManager (спека §1).
«Удалить» реально убирает строку — рабочий список id живёт в dialog_data,
хендлер on_click (получает SubManager, привязанный к строке) удаляет свой
item_id, и фреймворк перерисовывает окно. Jinja-текст над списком циклом по
оставшимся строкам читает состояние каждой через dialog_manager.find("lg") /
ManagedListGroup.find_for_item — демонстрирует ListGroup+SubManager+Jinja."""

from dataclasses import dataclass

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Button, Checkbox, ListGroup, Row
from vkbottle_dialog.widgets.text import Const, Format, Jinja

from .common import nav_row
from .states import ListDemo


@dataclass
class Item:
    id: str
    name: str


ITEMS = [
    Item("i1", "Первая строка"),
    Item("i2", "Вторая строка"),
    Item("i3", "Третья строка"),
]


def _live_ids(dialog_manager) -> list[str]:
    """Рабочий список id строк в dialog_data — инициализируется из ITEMS при
    первом показе, «удалить» вычёркивает отсюда."""
    ids = dialog_manager.dialog_data.get("item_ids")
    if ids is None:
        ids = [item.id for item in ITEMS]
        dialog_manager.dialog_data["item_ids"] = ids
    return ids


async def on_delete(event, button, manager) -> None:
    # manager — SubManager, привязанный к строке (item_id); dialog_data общий
    # с родительским контекстом, поэтому вычёркивание строки видно геттеру.
    ids = manager.dialog_data.get("item_ids")
    if ids is not None and manager.item_id in ids:
        ids.remove(manager.item_id)


async def list_demo_getter(dialog_manager, **kwargs) -> dict:
    live = set(_live_ids(dialog_manager))
    items = [item for item in ITEMS if item.id in live]
    lg = dialog_manager.find("lg")
    checked_names = [
        item.name
        for item in items
        if (chk := lg.find_for_item("chk", item.id)) is not None and chk.is_checked()
    ]
    return {"items": items, "checked_names": checked_names}


list_demo_dialog = Dialog(
    Window(
        Const("📋 ListGroup: строка = Checkbox + Button, состояние per-row через SubManager."),
        Jinja(
            "Отмечено:"
            "{% for name in checked_names %} {{ name }}{% if not loop.last %},{% endif %}"
            "{% endfor %}"
            "{% if not checked_names %} ничего{% endif %}"
        ),
        ListGroup(
            Row(
                Checkbox(Format("✅ {item.name}"), Format("⬜ {item.name}"), id="chk"),
                Button(
                    Const("🗑 удалить"), id="del", on_click=on_delete, snackbar="Строка удалена"
                ),
            ),
            id="lg",
            item_id_getter=lambda item: item.id,
            items="items",
        ),
        nav_row(),
        state=ListDemo.MAIN,
        getter=list_demo_getter,
    ),
)
