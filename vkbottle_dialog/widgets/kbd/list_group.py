from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ...exceptions import DialogConfigError
from ...manager.sub_manager import SubManager
from ..common import WhenCondition, get_items_getter
from .base import Keyboard, RawKeyboard
from .scroll import BaseScroll

ItemIdGetter = Callable[[Any], Any]


class ListGroup(Keyboard, BaseScroll):
    """Строка кнопок на каждый item, с состоянием, изолированным per-item
    через SubManager (widget_data[lg_id][item_id]). Callback детей
    отдаётся с префиксом "{lg_id}:{item_id}:{child_cb}".

    get_page/set_page ПЕРЕОПРЕДЕЛЕНЫ относительно BaseScroll: тот пишет
    int напрямую в widget_data[lg_id], но у ListGroup там лежит dict
    (строки, ключ — item_id) — страница хранится отдельно, под
    widget_data[lg_id][""]["_page"], иначе любой пейджер, привязанный к
    ListGroup, падает на первом же рендере с int(dict) TypeError."""

    def __init__(
        self,
        *buttons: Keyboard,
        id: str,
        item_id_getter: ItemIdGetter,
        items: Any,
        page_size: int = 0,
        on_page_changed: Callable | None = None,
        when: WhenCondition = None,
    ) -> None:
        Keyboard.__init__(self, id, when)
        BaseScroll.__init__(self, on_page_changed)
        self._buttons = buttons
        self._item_id_getter = item_id_getter
        self._items_getter = get_items_getter(items)
        self._page_size = page_size

    def _page_count(self, items: Sequence[Any]) -> int:
        if self._page_size == 0:
            return 1
        total = len(items)
        return total // self._page_size + bool(total % self._page_size)

    async def get_page_count(self, data: dict, manager: Any) -> int:
        if self._page_size == 0:
            return 1
        return self._page_count(self._items_getter(data))

    def get_page(self, manager: Any) -> int:
        row = manager.current_context().widget_data.setdefault(self.widget_id, {})
        return int(row.setdefault("", {}).get("_page", 0))

    async def set_page(self, manager: Any, page: int) -> None:
        row = manager.current_context().widget_data.setdefault(self.widget_id, {})
        row.setdefault("", {})["_page"] = int(page)
        await self._on_page_changed.process_event(
            getattr(manager, "event", None),
            self.managed(manager),
            manager,
            int(page),
        )

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        kbd: RawKeyboard = []
        items = self._items_getter(data)
        if self._page_size > 0:
            pages = self._page_count(items)
            page = min(max(pages - 1, 0), self.get_page(manager))
            offset = page * self._page_size
            items = items[offset : offset + self._page_size]
        else:
            offset = 0
        for pos, item in enumerate(items, offset):
            kbd.extend(await self._render_item(pos, item, data, manager))
        return kbd

    async def _render_item(self, pos: int, item: Any, data: dict, manager: Any) -> RawKeyboard:
        kbd: RawKeyboard = []
        item_id = str(self._item_id_getter(item))
        if ":" in item_id:
            raise DialogConfigError(
                f"ListGroup {self.widget_id!r}: item_id {item_id!r} не может "
                f"содержать ':' — конфликт с разделителем callback_data"
            )
        scoped = {"data": data, "item": item, "pos": pos + 1, "pos0": pos}
        sub_manager = SubManager(
            widget=self, manager=manager, widget_id=self._require_id(), item_id=item_id
        )
        for button in self._buttons:
            rows = await button.render_keyboard(scoped, sub_manager)
            for row in rows:
                for btn in row:
                    if btn.callback_data:
                        btn.callback_data = f"{self.widget_id}:{item_id}:{btn.callback_data}"
            kbd.extend(rows)
        return kbd

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

    def managed(self, manager: Any) -> ManagedListGroup:
        return ManagedListGroup(self, manager)


class ManagedListGroup:
    def __init__(self, widget: ListGroup, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def find_for_item(self, widget_id: str, item_id: str) -> Any | None:
        """Ищет виджет widget_id среди детей ListGroup и возвращает его
        managed-обёртку, привязанную к конкретной строке item_id — так
        код обработчиков может дёргать состояние строки, на которую
        пришёл клик, не дожидаясь следующего рендера."""
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
