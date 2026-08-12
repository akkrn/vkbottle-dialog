from __future__ import annotations

import math
from collections.abc import Callable
from datetime import time
from typing import Any

from ...exceptions import DialogConfigError
from ..common import WhenCondition, ensure_event_processor
from .base import ButtonColor, Keyboard, RawKeyboard, VKButton

_PER_PAGE = 8
_PER_ROW = 4


class TimeSelect(Keyboard):
    def __init__(
        self,
        id: str,
        on_click: Callable | None = None,
        on_value_changed: Callable | None = None,
        minute_precision: int = 30,
        hour_range: tuple[int, int] = (0, 24),
        selected_color: ButtonColor = ButtonColor.POSITIVE,
        when: WhenCondition = None,
    ) -> None:
        super().__init__(id, when)
        if minute_precision <= 0 or minute_precision > 60:
            raise DialogConfigError("TimeSelect: minute_precision должен быть в диапазоне 1..60")
        if hour_range[0] >= hour_range[1]:
            raise DialogConfigError("TimeSelect: hour_range[0] должен быть меньше hour_range[1]")
        self._on_click = ensure_event_processor(on_click)
        self._on_value_changed = ensure_event_processor(on_value_changed)
        self._precision = minute_precision
        self._hours = hour_range
        self._selected_color = selected_color

    def _slots(self) -> list[str]:
        return [
            f"{h:02d}:{m:02d}" for h in range(*self._hours) for m in range(0, 60, self._precision)
        ]

    def _state(self, manager: Any) -> dict:
        return self.get_widget_data(manager, {"value": None, "page": 0})

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        slots = self._slots()
        pages = max(1, math.ceil(len(slots) / _PER_PAGE))
        state = self._state(manager)
        page = min(int(state["page"]), pages - 1)
        selected = state["value"]
        kb: RawKeyboard = []
        row: list[VKButton] = []
        for slot in slots[page * _PER_PAGE : (page + 1) * _PER_PAGE]:
            color = self._selected_color if slot == selected else None
            row.append(VKButton("callback", slot, f"{self.widget_id}:t:{slot}", color=color))
            if len(row) == _PER_ROW:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        if pages > 1:
            kb.append(
                [
                    VKButton(
                        "callback",
                        "‹",
                        f"{self.widget_id}:p:{max(0, page - 1)}",
                    ),
                    VKButton(
                        "callback",
                        "›",
                        f"{self.widget_id}:p:{min(pages - 1, page + 1)}",
                    ),
                ]
            )
        return kb

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        kind, _, arg = item.partition(":")
        state = dict(self._state(manager))
        if kind == "p":
            try:
                target = int(arg)
            except ValueError:
                return False
            pages = max(1, math.ceil(len(self._slots()) / _PER_PAGE))
            state["page"] = max(0, min(target, pages - 1))
            self.set_widget_data(manager, state)
            return True
        if kind == "t":
            if arg not in self._slots():
                return False
            old = state["value"]
            state["value"] = arg
            self.set_widget_data(manager, state)
            hour, minute = arg.split(":")
            value = time(int(hour), int(minute))
            if arg != old:
                await self._on_value_changed.process_event(
                    manager.event, self.managed(manager), manager, value
                )
            await self._on_click.process_event(
                manager.event, self.managed(manager), manager, value
            )
            return True
        return False

    def managed(self, manager: Any) -> ManagedTimeSelect:
        return ManagedTimeSelect(self, manager)


class ManagedTimeSelect:
    def __init__(self, widget: TimeSelect, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def get_value(self) -> time | None:
        raw = self._widget._state(self._manager)["value"]
        if raw is None:
            return None
        hour, minute = raw.split(":")
        return time(int(hour), int(minute))

    def set_value(self, value: time) -> None:
        slots = self._widget._slots()
        target = f"{value.hour:02d}:{value.minute:02d}"
        if target not in slots:
            minutes = value.hour * 60 + value.minute
            target = min(
                slots,
                key=lambda s: abs(int(s[:2]) * 60 + int(s[3:]) - minutes),
            )
        state = dict(self._widget._state(self._manager))
        state["value"] = target
        self._widget.set_widget_data(self._manager, state)
