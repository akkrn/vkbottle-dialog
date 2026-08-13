"""Секция «VK-фишки»: VK-бонус сверх оригинала aiogram-dialog — цвета кнопок
(Button(color=...) все 4 ButtonColor), снекбары и вложенный диалог с
возвратом результата (Start дочернего диалога → on_process_result).

Дочерний диалог name_dialog (NameInput.INPUT) объявлен в этом же файле —
он крошечный (одно окно, один TextInput) и логически неотделим от секции,
которая его демонстрирует."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.input import TextInput
from vkbottle_dialog.widgets.kbd import Button, ButtonColor, Cancel, Group, Start, SwitchTo
from vkbottle_dialog.widgets.text import Const, Format

from .common import MAIN_MENU_BUTTON, nav_row
from .states import NameInput, VkFeatures


async def on_name_success(message, widget, manager, value) -> None:
    await manager.done({"name": value})


name_dialog = Dialog(
    Window(
        Const("Введите имя:"),
        TextInput(id="nm", on_success=on_name_success),
        Cancel(),
        state=NameInput.INPUT,
    ),
)


async def on_name_result(start_data, result, manager) -> None:
    if result:
        manager.dialog_data["name"] = result["name"]


def vk_features_getter(dialog_manager, **kwargs) -> dict:
    return {"name": dialog_manager.dialog_data.get("name")}


vk_features_dialog = Dialog(
    Window(
        Const("✨ VK-фишки"),
        Const("VK-бонус сверх оригинала: цвета кнопок, снекбары, вложенный диалог."),
        Group(
            SwitchTo(Const("🎨 Цвета кнопок"), id="to_colors", state=VkFeatures.COLORS),
            SwitchTo(Const("👤 Вложенный диалог"), id="to_nested", state=VkFeatures.NESTED),
            MAIN_MENU_BUTTON,
            width=2,
        ),
        state=VkFeatures.MAIN,
    ),
    Window(
        Const("🎨 Цвета кнопок"),
        Const("Button(color=...) — все 4 значения ButtonColor."),
        Group(
            Button(
                Const("Primary"),
                id="col_primary",
                color=ButtonColor.PRIMARY,
                snackbar="primary",
            ),
            Button(
                Const("Secondary"),
                id="col_secondary",
                color=ButtonColor.SECONDARY,
                snackbar="secondary",
            ),
            Button(
                Const("Positive"),
                id="col_positive",
                color=ButtonColor.POSITIVE,
                snackbar="positive",
            ),
            Button(
                Const("Negative"),
                id="col_negative",
                color=ButtonColor.NEGATIVE,
                snackbar="negative",
            ),
            width=2,
        ),
        nav_row(VkFeatures.MAIN),
        state=VkFeatures.COLORS,
    ),
    Window(
        Const("👤 Вложенный диалог"),
        Const("Start дочернего диалога, результат возвращается в dialog_data."),
        Format("Привет, {name}!", when="name"),
        Start(Const("Ввести имя"), id="ask", state=NameInput.INPUT),
        nav_row(VkFeatures.MAIN),
        state=VkFeatures.NESTED,
        getter=vk_features_getter,
    ),
    on_process_result=on_name_result,
)
