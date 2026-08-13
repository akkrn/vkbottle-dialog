from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from ...api.entities import CarouselElement, CarouselSpec
from ...exceptions import DialogConfigError
from ...limits import (
    CAROUSEL_DESC_MAX,
    CAROUSEL_MAX_BUTTONS,
    CAROUSEL_MAX_ELEMENTS,
    CAROUSEL_TITLE_MAX,
)
from ...manager.sub_manager import SubManager
from ..common import WhenCondition, get_items_getter
from ..media import Media
from ..text.base import Text
from .base import Keyboard, RawKeyboard, VKButton

logger = logging.getLogger("vkbottle_dialog")

ItemIdGetter = Callable[[Any], Any]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class Carousel(Keyboard):
    """VK-карусель (template) — Keyboard-подкласс в keyboard-слоте (как
    ListGroup — переиспользует его item-prefix диспатч и SubManager-scoping,
    но render_keyboard пуст: содержимое идёт не в inline-кнопки, а в
    отдельную структуру CarouselSpec, которую Window.render кладёт в
    NewMessage.carousel — MessageManager резолвит photo и собирает итоговый
    template-JSON (спека §5)."""

    def __init__(
        self,
        id: str,
        items: Any,
        item_id_getter: ItemIdGetter,
        title: Text,
        description: Text,
        buttons: Sequence[Keyboard],
        photo: Media | None = None,
        element_action: str | None = None,
        element_url: Text | None = None,
        when: WhenCondition = None,
    ) -> None:
        super().__init__(id, when)
        if element_action not in (None, "open_link", "open_photo"):
            raise DialogConfigError(
                f"Carousel: element_action должен быть 'open_link'/'open_photo'/None, "
                f"получено {element_action!r}"
            )
        if element_action == "open_link" and element_url is None:
            raise DialogConfigError("Carousel: element_action='open_link' требует element_url")
        self._buttons: Sequence[Keyboard] = buttons
        self._items_getter = get_items_getter(items)
        self._item_id_getter = item_id_getter
        self._title = title
        self._description = description
        self._photo = photo
        self._element_action = element_action
        self._element_url = element_url

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        return []

    async def render_carousel(self, data: dict, manager: Any) -> CarouselSpec | None:
        if not self.is_(data, manager):
            return None
        items = list(self._items_getter(data))
        if len(items) > CAROUSEL_MAX_ELEMENTS:
            items = items[:CAROUSEL_MAX_ELEMENTS]
            logger.warning(
                "Carousel %r: элементов больше %s — усечено до %s (данные динамические)",
                self.widget_id,
                CAROUSEL_MAX_ELEMENTS,
                CAROUSEL_MAX_ELEMENTS,
            )
        if not items:
            return None
        elements: list[CarouselElement] = []
        first_shape: tuple[bool, int] | None = None
        for pos, item in enumerate(items):
            item_id = str(self._item_id_getter(item))
            if ":" in item_id:
                raise DialogConfigError(
                    f"Carousel {self.widget_id!r}: item_id {item_id!r} не может "
                    f"содержать ':' — конфликт с разделителем callback_data"
                )
            element = await self._render_element(pos, item, item_id, data, manager)
            shape = (element.photo is not None, len(element.buttons))
            if first_shape is None:
                first_shape = shape
            elif shape != first_shape:
                raise DialogConfigError(
                    f"Carousel {self.widget_id!r}: элемент {item_id!r} структурно "
                    f"отличается от первого (наличие photo/число кнопок) — VK требует "
                    f"одинаковую структуру у всех элементов карусели"
                )
            elements.append(element)
        return CarouselSpec(elements=elements)

    async def _render_element(
        self, pos: int, item: Any, item_id: str, data: dict, manager: Any
    ) -> CarouselElement:
        scoped = {"data": data, "item": item, "pos": pos + 1, "pos0": pos}
        sub_manager = SubManager(
            widget=self, manager=manager, widget_id=self._require_id(), item_id=item_id
        )
        title = _truncate(await self._title.render_text(scoped, sub_manager), CAROUSEL_TITLE_MAX)
        description = _truncate(
            await self._description.render_text(scoped, sub_manager), CAROUSEL_DESC_MAX
        )
        photo = await self._photo.render_media(scoped, sub_manager) if self._photo else None
        buttons: list[VKButton] = []
        for button in self._buttons:
            rows = await button.render_keyboard(scoped, sub_manager)
            for row in rows:
                for btn in row:
                    if btn.callback_data:
                        btn.callback_data = f"{self.widget_id}:{item_id}:{btn.callback_data}"
                    buttons.append(btn)
        if len(buttons) > CAROUSEL_MAX_BUTTONS:
            raise DialogConfigError(
                f"Carousel {self.widget_id!r}: элемент {item_id!r} — {len(buttons)} кнопок "
                f"> {CAROUSEL_MAX_BUTTONS}"
            )
        action: dict[str, str] | None = None
        if self._element_action == "open_link":
            assert self._element_url is not None
            link = await self._element_url.render_text(scoped, sub_manager)
            action = {"type": "open_link", "link": link}
        elif self._element_action == "open_photo":
            action = {"type": "open_photo"}
        return CarouselElement(
            title=title, description=description, photo=photo, buttons=buttons, action=action
        )

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        try:
            item_id, child_cb = item.split(":", 1)
        except ValueError:
            return False
        sub_manager = SubManager(
            widget=self, manager=manager, widget_id=self._require_id(), item_id=item_id
        )
        for button in self._buttons:
            if await button.process_callback(child_cb, sub_manager):
                return True
        return False

    def find(self, widget_id: str) -> Any:
        if self.widget_id == widget_id:
            return self
        for button in self._buttons:
            found = button.find(widget_id)
            if found is not None:
                return found
        return None

    def managed(self, manager: Any) -> ManagedCarousel:
        return ManagedCarousel(self, manager)


class ManagedCarousel:
    def __init__(self, widget: Carousel, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def find_for_item(self, widget_id: str, item_id: str) -> Any | None:
        widget = self._widget.find(widget_id)
        if widget is None:
            return None
        sub_manager = SubManager(
            widget=self._widget,
            manager=self._manager,
            widget_id=self._widget._require_id(),
            item_id=str(item_id),
        )
        return widget.managed(sub_manager)
