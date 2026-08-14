"""Секция «Карусель»: 3-элементная VK-карусель товаров (title/description/
photo + callback-кнопка «Выбрать» со снекбаром на элемент). Carousel рендерит
не inline-клавиатуру, а template (спека §5) — окно занимает keyboard-слот
целиком, поэтому нижняя навигация идёт отдельной callback-клавиатурой
(TextKeyboardFactory), а не inline-кнопкой рядом с элементами.

Работает только в личных сообщениях: TextKeyboardFactory (нижняя навигация)
в беседе поднимает DialogConfigError (см. window.py) — общая клавиатура на
весь чат, точно так же, как секция «Нижняя клавиатура». Секция помечена
«(ЛС)» и в тексте окна, и в главном меню."""

from dataclasses import dataclass
from pathlib import Path

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import Button, Carousel
from vkbottle_dialog.widgets.markup import TextKeyboardFactory
from vkbottle_dialog.widgets.media import StaticMedia
from vkbottle_dialog.widgets.text import Const, Format

from .common import nav_row
from .states import CarouselDemo

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
            "🎠 Карусель (ЛС) — VK template, не inline-кнопки. Нижняя навигация — "
            "callback-клавиатура (TextKeyboardFactory), потому что карусель "
            "занимает keyboard-слот окна целиком. В беседе такое окно упадёт с "
            "DialogConfigError — общая клавиатура на весь чат, только для ЛС."
        ),
        Carousel(
            id="car",
            items="products",
            item_id_getter=lambda p: p.id,
            title=Format("{item.name}"),
            description=Format("{item.description}"),
            photo=StaticMedia(path=Format(str(MEDIA_DIR / "{item.photo}"))),
            buttons=[Button(Const("Выбрать"), id="pick", snackbar="Товар выбран (демо)")],
        ),
        nav_row(),
        state=CarouselDemo.MAIN,
        markup_factory=TextKeyboardFactory(button_type="callback"),
        getter=carousel_demo_getter,
    ),
)
