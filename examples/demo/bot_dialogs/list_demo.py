"""Секция «ListGroup»: 3 строки, каждая — Checkbox «выбрать»+item.name и
Button «удалить» (снекбар), состояние изолировано per-row через SubManager
(спека §1). Jinja-текст над списком циклом по ITEMS читает состояние каждой
строки через dialog_manager.find("lg") / ManagedListGroup.find_for_item —
демонстрирует ListGroup+SubManager+Jinja вместе."""

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


async def list_demo_getter(dialog_manager, **kwargs) -> dict:
    lg = dialog_manager.find("lg")
    checked_names = [
        item.name
        for item in ITEMS
        if (chk := lg.find_for_item("chk", item.id)) is not None and chk.is_checked()
    ]
    return {"items": ITEMS, "checked_names": checked_names}


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
                Button(Const("🗑 удалить"), id="del", snackbar="Строка «удалена» (демо)"),
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
