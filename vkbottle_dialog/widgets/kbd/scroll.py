from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from ..common import WhenCondition, ensure_event_processor
from .base import Keyboard, RawKeyboard, VKButton
from .group import Group


class BaseScroll:
    widget_id: str | None

    def __init__(self, on_page_changed: Callable | None = None) -> None:
        self._on_page_changed = ensure_event_processor(on_page_changed)

    def get_page(self, manager: Any) -> int:
        return int(manager.current_context().widget_data.get(self.widget_id, 0))

    async def set_page(self, manager: Any, page: int) -> None:
        manager.current_context().widget_data[self.widget_id] = int(page)
        await self._on_page_changed.process_event(
            getattr(manager, "event", None), self, manager, page,
        )

    async def get_page_count(self, data: dict, manager: Any) -> int:
        raise NotImplementedError


class ScrollingGroup(Group, BaseScroll):
    def __init__(self, *kbds: Keyboard, id: str, height: int,
                 width: int | None = None, hide_pager: bool = False,
                 on_page_changed: Callable | None = None,
                 when: WhenCondition = None) -> None:
        Group.__init__(self, *kbds, width=width, id=id, when=when)
        BaseScroll.__init__(self, on_page_changed)
        self._height = height
        self._hide_pager = hide_pager

    async def _rows(self, data: dict, manager: Any) -> RawKeyboard:
        return await Group._render_keyboard(self, data, manager)

    async def get_page_count(self, data: dict, manager: Any) -> int:
        rows = await self._rows(data, manager)
        return max(1, math.ceil(len(rows) / self._height))

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        rows = await self._rows(data, manager)
        pages = max(1, math.ceil(len(rows) / self._height))
        page = min(self.get_page(manager), pages - 1)
        start = page * self._height
        kbd = rows[start:start + self._height]
        if pages > 1 and not self._hide_pager:
            kbd.append(self._pager_row(page, pages))
        return kbd

    def _pager_row(self, page: int, pages: int) -> list[VKButton]:
        def btn(label: str, target: int) -> VKButton:
            return VKButton(action="callback", label=label,
                            callback_data=f"{self.widget_id}:{target}")
        return [
            btn("«", 0),
            btn("‹", max(0, page - 1)),
            btn(f"{page + 1}/{pages}", page),
            btn("›", min(pages - 1, page + 1)),
            btn("»", pages - 1),
        ]

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        try:
            page = int(item)
        except ValueError:
            return False
        data = await manager.load_data() if hasattr(manager, "load_data") else {}
        pages = await self.get_page_count(data, manager)
        await self.set_page(manager, max(0, min(page, pages - 1)))
        return True


class StubScroll(Keyboard, BaseScroll):
    def __init__(self, id: str, pages: Any,
                 on_page_changed: Callable | None = None) -> None:
        Keyboard.__init__(self, id, None)
        BaseScroll.__init__(self, on_page_changed)
        self._pages = pages  # str-ключ данных либо callable(data) -> int

    async def get_page_count(self, data: dict, manager: Any) -> int:
        if callable(self._pages):
            return int(self._pages(data))
        return int(data.get(self._pages, 1))

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        return []

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        try:
            page = int(item)
        except ValueError:
            return False
        data = await manager.load_data() if hasattr(manager, "load_data") else {}
        pages = await self.get_page_count(data, manager)
        await self.set_page(manager, max(0, min(page, pages - 1)))
        return True


def sync_scroll(*scroll_ids: str) -> Callable:
    async def on_page_changed(event: Any, widget: Any, manager: Any, page: int) -> None:
        for sid in scroll_ids:
            target = manager.find_scroll(sid)
            if target is not widget:
                target_ctx = manager.current_context()
                target_ctx.widget_data[sid] = int(page)
    return on_page_changed
