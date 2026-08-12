"""Секция «Селекты»: Select/Radio/Multiselect/Toggle на общем списке фруктов
показывают базовые сценарии выбора одного/нескольких элементов."""

from dataclasses import dataclass

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Column, Group, Multiselect, Radio, Select, SwitchTo, Toggle
from vkbottle_dialog.widgets.text import Const, Format

from .common import MAIN_MENU_BUTTON, nav_row
from .states import Selects


@dataclass
class Fruit:
    id: str
    name: str


FRUITS = [
    Fruit("apple", "Яблоко"),
    Fruit("banana", "Банан"),
    Fruit("orange", "Апельсин"),
    Fruit("pear", "Груша"),
]

TOGGLE_ITEMS = ["😆", "😱", "🤖", "🤡"]


async def fruits_getter(**kwargs) -> dict:
    return {"fruits": FRUITS}


async def on_select_click(event, widget, manager, item_id) -> None:
    fruit = next(f for f in FRUITS if f.id == item_id)
    await manager.answer(snackbar=f"Выбрано: {fruit.name}")


selects_dialog = Dialog(
    Window(
        Const("☑️ Селекты: списки с выбором"),
        Const("Выберите подсекцию:"),
        Group(
            SwitchTo(Const("Select"), id="to_select", state=Selects.SELECT),
            SwitchTo(Const("Radio"), id="to_radio", state=Selects.RADIO),
            SwitchTo(Const("Multiselect"), id="to_multi", state=Selects.MULTI),
            SwitchTo(Const("Toggle"), id="to_toggle", state=Selects.TOGGLE),
            MAIN_MENU_BUTTON,
            width=2,
        ),
        state=Selects.MAIN,
    ),
    Window(
        Const("Select — клик по любому пункту шлёт снекбар с выбором."),
        Column(
            Select(
                Format("{item.name}"),
                id="sel",
                item_id_getter=lambda f: f.id,
                items="fruits",
                on_click=on_select_click,
            ),
        ),
        nav_row(Selects.MAIN),
        state=Selects.SELECT,
        getter=fruits_getter,
    ),
    Window(
        Const("Radio — выбор одного варианта, отмеченный элемент подсвечен."),
        Column(
            Radio(
                Format("🔘 {item.name}"),
                Format("⚪ {item.name}"),
                id="rad",
                item_id_getter=lambda f: f.id,
                items="fruits",
            ),
        ),
        nav_row(Selects.MAIN),
        state=Selects.RADIO,
        getter=fruits_getter,
    ),
    Window(
        Const("Multiselect — можно отметить сразу несколько вариантов."),
        Column(
            Multiselect(
                Format("✓ {item.name}"),
                Format("{item.name}"),
                id="ms",
                item_id_getter=lambda f: f.id,
                items="fruits",
            ),
        ),
        nav_row(Selects.MAIN),
        state=Selects.MULTI,
        getter=fruits_getter,
    ),
    Window(
        Const("Toggle — одна кнопка, клик циклически переключает значение."),
        Toggle(Format("{item}"), id="tog", items=TOGGLE_ITEMS),
        nav_row(Selects.MAIN),
        state=Selects.TOGGLE,
    ),
)
