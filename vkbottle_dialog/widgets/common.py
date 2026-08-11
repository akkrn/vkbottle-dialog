from __future__ import annotations

import re
from typing import Any, Callable, Sequence, Union

from magic_filter import MagicFilter

from ..exceptions import DialogConfigError

WIDGET_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.]+$")
WhenCondition = Union[str, MagicFilter, Callable, None]


class Whenable:
    def __init__(self, when: WhenCondition = None) -> None:
        self._when = when

    def is_(self, data: dict, manager: Any) -> bool:
        if self._when is None:
            return True
        if isinstance(self._when, str):
            return bool(data.get(self._when))
        if isinstance(self._when, MagicFilter):
            return bool(self._when.resolve(data))
        return bool(self._when(data, self, manager))


class Actionable:
    def __init__(self, id: str | None = None) -> None:
        if id is not None and not WIDGET_ID_PATTERN.match(id):
            raise DialogConfigError(f"недопустимый widget id: {id!r}")
        self.widget_id = id

    def get_widget_data(self, manager: Any, default: Any) -> Any:
        return manager.current_context().widget_data.get(self.widget_id, default)

    def set_widget_data(self, manager: Any, value: Any) -> None:
        manager.current_context().widget_data[self.widget_id] = value

    def find(self, widget_id: str) -> Any:
        return self if self.widget_id == widget_id else None

    def managed(self, manager: Any) -> Any:
        return self


class WidgetEventProcessor:
    def __init__(self, handler: Callable | None) -> None:
        self._handler = handler

    async def process_event(self, *args: Any) -> None:
        if self._handler is not None:
            await self._handler(*args)


def ensure_event_processor(handler: Callable | None) -> WidgetEventProcessor:
    if isinstance(handler, WidgetEventProcessor):
        return handler
    return WidgetEventProcessor(handler)


def ensure_data_getter(getter: Any) -> Callable:
    if getter is None:
        async def empty(**kwargs: Any) -> dict:
            return {}
        return empty
    if isinstance(getter, dict):
        async def const(**kwargs: Any) -> dict:
            return dict(getter)
        return const
    if callable(getter):
        async def call(**kwargs: Any) -> dict:
            return await getter(**kwargs) or {}
        return call
    raise DialogConfigError(f"не понимаю getter: {getter!r}")


def get_items_getter(items: Any) -> Callable[[dict], Sequence]:
    if isinstance(items, str):
        return lambda data: data.get(items, [])
    if isinstance(items, MagicFilter):
        return lambda data: items.resolve(data) or []
    if callable(items):
        return lambda data: items(data)
    if isinstance(items, Sequence):
        return lambda data: items
    raise DialogConfigError(f"не понимаю items: {items!r}")
