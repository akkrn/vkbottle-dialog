"""Секция «Карусель»: 3-элементная VK-карусель товаров (title/description/
photo + callback-кнопки на элемент). Carousel рендерит не inline-клавиатуру,
а template (спека §5) — и VK НЕ принимает keyboard вместе с template (ошибка
100 «Only template or keyboard field should be specified»). Поэтому вся
навигация живёт кнопками ВНУТРИ элементов карусели: на каждом товаре — «Выбрать»
(снекбар) и «☰ Меню» (возврат в главное меню через Start). Структура элементов
одинаковая (VK требует униформности), так что обе кнопки есть на каждом.

Карусель работает и в личке, и в беседах — нижней клавиатуры больше нет, а
template VK принимает в обоих контекстах."""

from dataclasses import dataclass
from pathlib import Path

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Button, Carousel, Start
from vkbottle_dialog.widgets.media import StaticMedia
from vkbottle_dialog.widgets.text import Const, Format

from .states import CarouselDemo, Main

MEDIA_DIR = Path(__file__).parent.parent / "media"


@dataclass
class Product:
    id: str
    name: str
    description: str
    photo: str  # имя файла в media/


PRODUCTS = [
    Product("p1", "Товар 1", "Первый демо-товар карусели — фото из media/1.png.", "1.png"),
    Product("p2", "Товар 2", "Второй демо-товар, описание короче.", "2.png"),
    Product("p3", "Товар 3", "Третий демо-товар, для примера структуры.", "3.png"),
]


async def carousel_demo_getter(**kwargs) -> dict:
    return {"products": PRODUCTS}


carousel_demo_dialog = Dialog(
    Window(
        Const(
            "🎠 Карусель — VK template, не inline-кнопки. Навигация — кнопками "
            "внутри карточек («☰ Меню»), потому что VK не принимает обычную "
            "клавиатуру вместе с template. Работает и в ЛС, и в беседах."
        ),
        Carousel(
            id="car",
            items="products",
            item_id_getter=lambda p: p.id,
            title=Format("{item.name}"),
            description=Format("{item.description}"),
            photo=StaticMedia(path=Format(str(MEDIA_DIR / "{item.photo}"))),
            buttons=[
                Button(Const("Выбрать"), id="pick", snackbar="Товар выбран (демо)"),
                Start(Const("☰ Меню"), id="menu", state=Main.MAIN),
            ],
        ),
        state=CarouselDemo.MAIN,
        getter=carousel_demo_getter,
    ),
)
