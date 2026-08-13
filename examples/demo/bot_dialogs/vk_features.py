"""Секция «VK-фишки»: VK-бонус сверх оригинала aiogram-dialog — цвета кнопок
(Button(color=...) все 4 ButtonColor), снекбары, вложенный диалог с
возвратом результата (Start дочернего диалога → on_process_result) и
DynamicMedia — геттер сам решает, какое MediaAttachment показать (в отличие
от StaticMedia, где путь/url фиксирован в Text-виджете).

Дочерний диалог name_dialog (NameInput.INPUT) объявлен в этом же файле —
он крошечный (одно окно, один TextInput) и логически неотделим от секции,
которая его демонстрирует."""

from pathlib import Path

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.api.entities import MediaAttachment
from vkbottle_dialog.widgets.input import TextInput
from vkbottle_dialog.widgets.kbd import Button, ButtonColor, Cancel, Group, Start, SwitchTo
from vkbottle_dialog.widgets.media import DynamicMedia
from vkbottle_dialog.widgets.text import Const, Format

from .common import MAIN_MENU_BUTTON, nav_row
from .states import NameInput, VkFeatures

MEDIA_DIR = Path(__file__).parent.parent / "media"
DYNAMIC_PHOTOS = ["1.png", "2.png", "3.png"]


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


def dynamic_media_getter(dialog_manager, **kwargs) -> dict:
    idx = dialog_manager.dialog_data.get("dyn_idx", 0)
    photo = DYNAMIC_PHOTOS[idx % len(DYNAMIC_PHOTOS)]
    return {
        "dyn_media": MediaAttachment(path=str(MEDIA_DIR / photo)),
        "dyn_photo": photo,
    }


async def on_dyn_next(event, widget, manager) -> None:
    manager.dialog_data["dyn_idx"] = manager.dialog_data.get("dyn_idx", 0) + 1


vk_features_dialog = Dialog(
    Window(
        Const("✨ VK-фишки"),
        Const("VK-бонус сверх оригинала: цвета кнопок, снекбары, вложенный диалог."),
        Group(
            SwitchTo(Const("🎨 Цвета кнопок"), id="to_colors", state=VkFeatures.COLORS),
            SwitchTo(Const("👤 Вложенный диалог"), id="to_nested", state=VkFeatures.NESTED),
            SwitchTo(
                Const("🖼 Динамическое медиа"),
                id="to_dynamic_media",
                state=VkFeatures.DYNAMIC_MEDIA,
            ),
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
    Window(
        Const("🖼 Динамическое медиа"),
        Const("DynamicMedia — геттер сам решает, что показать (в отличие от StaticMedia)."),
        Format("Сейчас: {dyn_photo}"),
        DynamicMedia("dyn_media"),
        Button(Const("Следующее фото"), id="dyn_next", on_click=on_dyn_next),
        nav_row(VkFeatures.MAIN),
        state=VkFeatures.DYNAMIC_MEDIA,
        getter=dynamic_media_getter,
    ),
    on_process_result=on_name_result,
)
