from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .api.entities import CarouselSpec, EventContext, NewMessage
from .exceptions import DialogConfigError
from .fsm import State
from .payload import encode_payload
from .widgets.common import ensure_data_getter, ensure_event_processor
from .widgets.kbd.carousel import Carousel
from .widgets.kbd.scroll import BaseScroll
from .widgets.markup import TextKeyboardFactory
from .widgets.utils import ensure_widgets


def _flatten_keyboards(widget: Any) -> list[Any]:
    # Group/Row/Column хранят детей в _kbds — плоский обход нужен только
    # затем, чтобы найти Carousel среди возможных обёрток и посчитать,
    # остались ли РЯДОМ другие клавиатурные виджеты (карусель — не
    # inline-кнопки, см. Carousel.render_keyboard → []).
    kbds = getattr(widget, "_kbds", None)
    if kbds is None:
        return [widget]
    flat: list[Any] = []
    for child in kbds:
        flat.extend(_flatten_keyboards(child))
    return flat


def _encode_carousel_payloads(spec: CarouselSpec, intent_id: str, secret: str | None) -> None:
    for element in spec.elements:
        for btn in element.buttons:
            if btn.callback_data:
                btn.callback_data = encode_payload(intent_id, btn.callback_data, secret)


class Window:
    def __init__(
        self,
        *widgets: Any,
        state: State,
        getter: Any = None,
        markup_factory: Any = None,
        on_process_result: Callable | None = None,
        disable_mentions: bool = True,
        dont_parse_links: bool = False,
    ) -> None:
        self._text, self._keyboard, self._input, self._media = ensure_widgets(widgets)
        self.state = state
        self._getter = ensure_data_getter(getter)
        self._markup_factory = markup_factory
        self._on_process_result = ensure_event_processor(on_process_result)
        self._disable_mentions = disable_mentions
        self._dont_parse_links = dont_parse_links
        self._carousel = self._detect_carousel()

    def _detect_carousel(self) -> Carousel | None:
        flat = _flatten_keyboards(self._keyboard)
        carousels = [w for w in flat if isinstance(w, Carousel)]
        if len(carousels) > 1:
            raise DialogConfigError("Window: в одном окне допустим только один Carousel")
        if not carousels:
            return None
        carousel = carousels[0]
        if len(flat) > 1 and not isinstance(self._markup_factory, TextKeyboardFactory):
            raise DialogConfigError(
                "Carousel нельзя сочетать с другими клавиатурными виджетами в том же "
                "окне без markup_factory=TextKeyboardFactory(...) для нижней навигации "
                "(спека §5: карусель занимает keyboard-слот целиком)"
            )
        return carousel

    async def load_data(self, manager: Any) -> dict:
        # Геттеры (global/dialog/window) уже применены внутри
        # manager.load_data() — единая точка правды, чтобы данные
        # callback-времени (виджеты вроде ScrollingGroup зовут
        # manager.load_data() напрямую) совпадали с данными рендера.
        return await manager.load_data()

    async def load_getter_data(self, manager: Any) -> dict:
        kwargs = {**getattr(manager, "middleware_data", {}), "dialog_manager": manager}
        return await self._getter(**kwargs)

    async def render(
        self,
        manager: Any,
        event_ctx: EventContext,
        intent_id: str,
        secret: str | None,
        default_markup_factory: Any,
    ) -> NewMessage:
        factory = self._markup_factory or default_markup_factory
        if isinstance(factory, TextKeyboardFactory) and event_ctx.is_chat:
            raise DialogConfigError(
                "TextKeyboardFactory нельзя использовать в беседах: нижняя "
                "клавиатура общая на чат (спека §6)"
            )
        data = await self.load_data(manager)
        text = await self._text.render_text(data, manager)
        raw_kbd = await self._keyboard.render_keyboard(data, manager)
        rendered = factory.render(raw_kbd, intent_id, secret)
        media = await self._media.render_media(data, manager) if self._media else None
        carousel_spec = None
        if self._carousel is not None:
            carousel_spec = await self._carousel.render_carousel(data, manager)
            if carousel_spec is not None:
                _encode_carousel_payloads(carousel_spec, intent_id, secret)
        return NewMessage(
            peer_id=event_ctx.peer_id,
            text=text or " ",
            keyboard=rendered.json,
            keyboard_kind=rendered.kind,
            disable_mentions=self._disable_mentions,
            dont_parse_links=self._dont_parse_links,
            media=media,
            carousel=carousel_spec,
        )

    async def process_callback(self, callback_data: str, manager: Any) -> bool:
        return await self._keyboard.process_callback(callback_data, manager)

    async def process_message(self, message: Any, manager: Any) -> bool:
        if self._input is None:
            return False
        return await self._input.process_message(message, manager)

    async def process_result(self, start_data: Any, result: Any, manager: Any) -> None:
        await self._on_process_result.process_event(start_data, result, manager)

    def find(self, widget_id: str) -> Any:
        for slot in (self._text, self._keyboard, self._input):
            if slot is not None:
                found = slot.find(widget_id)
                if found is not None:
                    return found
        return None

    def find_scroll(self, widget_id: str) -> BaseScroll | None:
        found = self.find(widget_id)
        return found if isinstance(found, BaseScroll) else None
