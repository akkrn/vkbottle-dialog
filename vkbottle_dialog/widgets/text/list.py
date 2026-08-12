from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from ...exceptions import DialogConfigError
from ..common import Actionable, WhenCondition, get_items_getter
from ..kbd.scroll import BaseScroll
from .base import Text


class List(Text, Actionable, BaseScroll):
    def __init__(self, field: Text, items: Any, sep: str = "\n",
                 id: str | None = None, page_size: int | None = None,
                 on_page_changed: Callable | None = None,
                 when: WhenCondition = None) -> None:
        # Явная инициализация баз: Whenable.__init__ не зовёт super()
        Text.__init__(self, when)
        Actionable.__init__(self, id)
        BaseScroll.__init__(self, on_page_changed)
        if page_size is not None and id is None:
            raise DialogConfigError("List(page_size=...) требует id")
        self._field = field
        self._items = get_items_getter(items)
        self._sep = sep
        self._page_size = page_size

    async def get_page_count(self, data: dict, manager: Any) -> int:
        items = list(self._items(data))
        if not items or not self._page_size:
            return 0 if not items else 1
        return math.ceil(len(items) / self._page_size)

    async def _render_text(self, data: dict, manager: Any) -> str:
        items = list(self._items(data))
        start = 0
        pages = 1
        page = 0
        if self._page_size is not None and items:
            pages = math.ceil(len(items) / self._page_size)
            page = min(self.get_page(manager), pages - 1)
            start = page * self._page_size
            items_slice = items[start:start + self._page_size]
        else:
            items_slice = items
        parts = []
        for offset, item in enumerate(items_slice):
            pos0 = start + offset
            scoped = {"data": data, "item": item, "pos": pos0 + 1,
                      "pos0": pos0, "current_page": page,
                      "current_page1": page + 1, "pages": pages}
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
