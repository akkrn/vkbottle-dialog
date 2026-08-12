from __future__ import annotations

from typing import Any

from ..common import WhenCondition, get_items_getter
from .base import Text


class List(Text):
    def __init__(
        self, field: Text, items: Any, sep: str = "\n", when: WhenCondition = None
    ) -> None:
        super().__init__(when)
        self._field = field
        self._items = get_items_getter(items)
        self._sep = sep

    async def _render_text(self, data: dict, manager: Any) -> str:
        parts = []
        for pos, item in enumerate(self._items(data)):
            scoped = {"data": data, "item": item, "pos": pos + 1, "pos0": pos}
            parts.append(await self._field.render_text(scoped, manager))
        return self._sep.join(p for p in parts if p)


class Progress(Text):
    def __init__(
        self,
        field: str,
        width: int = 10,
        filled: str = "█",
        empty: str = "░",
        when: WhenCondition = None,
    ) -> None:
        super().__init__(when)
        self._field = field
        self._width = width
        self._filled = filled
        self._empty = empty

    async def _render_text(self, data: dict, manager: Any) -> str:
        percent = max(0.0, min(100.0, float(data.get(self._field, 0))))
        done = round(self._width * percent / 100)
        return self._filled * done + self._empty * (self._width - done)
