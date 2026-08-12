from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from ..common import Actionable, WhenCondition
from ..kbd.scroll import BaseScroll
from .base import Text


class ScrollingText(Text, Actionable, BaseScroll):
    """Плоский посимвольный срез, как в оригинале aiogram-dialog."""

    def __init__(self, text: Text, id: str, page_size: int,
                 on_page_changed: Callable | None = None,
                 when: WhenCondition = None) -> None:
        Text.__init__(self, when)
        Actionable.__init__(self, id)
        BaseScroll.__init__(self, on_page_changed)
        self._text = text
        self._page_size = page_size

    async def get_page_count(self, data: dict, manager: Any) -> int:
        rendered = await self._text.render_text(data, manager)
        if not rendered:
            return 0
        return math.ceil(len(rendered) / self._page_size)

    def find(self, widget_id: str) -> Any:
        return self if widget_id == self.widget_id else None

    async def _render_text(self, data: dict, manager: Any) -> str:
        rendered = await self._text.render_text(data, manager)
        if not rendered:
            return ""
        pages = math.ceil(len(rendered) / self._page_size)
        page = min(self.get_page(manager), pages - 1)
        offset = page * self._page_size
        return rendered[offset:offset + self._page_size]
