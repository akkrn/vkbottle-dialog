from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..common import WhenCondition, ensure_event_processor
from ..text.base import Const, Format, Text
from .base import ButtonColor, Keyboard, RawKeyboard, VKButton

_DEFAULT_TEXT = Format("{value:g}")
_DEFAULT_MINUS = Const("−")
_DEFAULT_PLUS = Const("+")


class Counter(Keyboard):
    def __init__(
        self,
        id: str,
        default: float = 0,
        min_value: float = 0,
        max_value: float = 999999,
        increment: float = 1,
        cycle: bool = False,
        text: Text | None = _DEFAULT_TEXT,
        minus: Text | None = _DEFAULT_MINUS,
        plus: Text | None = _DEFAULT_PLUS,
        minus_color: ButtonColor | None = ButtonColor.NEGATIVE,
        plus_color: ButtonColor | None = ButtonColor.POSITIVE,
        on_click: Callable | None = None,
        on_value_changed: Callable | None = None,
        on_text_click: Callable | None = None,
        when: WhenCondition = None,
    ) -> None:
        super().__init__(id, when)
        self._default = float(default)
        self._min = float(min_value)
        self._max = float(max_value)
        self._increment = float(increment)
        self._cycle = cycle
        self._text = text
        self._minus = minus
        self._plus = plus
        self._minus_color = minus_color
        self._plus_color = plus_color
        self._on_click = ensure_event_processor(on_click)
        self._on_value_changed = ensure_event_processor(on_value_changed)
        self._on_text_click = ensure_event_processor(on_text_click)

    def get_value(self, manager: Any) -> float:
        return float(self.get_widget_data(manager, self._default))

    def _clamp(self, value: float) -> float:
        return max(self._min, min(self._max, value))

    async def _set_value(self, manager: Any, value: float) -> None:
        old = self.get_value(manager)
        value = self._clamp(value)
        self.set_widget_data(manager, value)
        if value != old:
            await self._on_value_changed.process_event(
                manager.event, self.managed(manager), manager
            )

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        value = self.get_value(manager)
        scoped = {"data": data, "value": value}
        row: list[VKButton] = []
        if self._minus is not None:
            row.append(
                VKButton(
                    action="callback",
                    label=await self._minus.render_text(scoped, manager),
                    callback_data=f"{self.widget_id}:-",
                    color=self._minus_color,
                )
            )
        if self._text is not None:
            row.append(
                VKButton(
                    action="callback",
                    label=await self._text.render_text(scoped, manager),
                    callback_data=f"{self.widget_id}:t",
                    color=None,
                )
            )
        if self._plus is not None:
            row.append(
                VKButton(
                    action="callback",
                    label=await self._plus.render_text(scoped, manager),
                    callback_data=f"{self.widget_id}:+",
                    color=self._plus_color,
                )
            )
        return [row] if row else []

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        value = self.get_value(manager)
        if item == "+":
            new = value + self._increment
            if new > self._max:
                if not self._cycle:
                    return True  # тихий no-op
                new = self._min
            await self._set_value(manager, new)
        elif item == "-":
            new = value - self._increment
            if new < self._min:
                if not self._cycle:
                    return True
                new = self._max
            await self._set_value(manager, new)
        elif item == "t":
            await self._on_text_click.process_event(manager.event, self.managed(manager), manager)
        else:
            return False
        await self._on_click.process_event(manager.event, self.managed(manager), manager)
        return True

    def managed(self, manager: Any) -> ManagedCounter:
        return ManagedCounter(self, manager)


class ManagedCounter:
    def __init__(self, widget: Counter, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def get_value(self) -> float:
        return self._widget.get_value(self._manager)

    def set_value(self, value: float) -> None:
        self._widget.set_widget_data(self._manager, self._widget._clamp(float(value)))
