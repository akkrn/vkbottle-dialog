from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..common import Actionable, Whenable, WhenCondition


class ButtonColor(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    NEGATIVE = "negative"
    POSITIVE = "positive"


@dataclass
class VKButton:
    action: str  # "callback" | "text" | "open_link"
    label: str
    callback_data: str | None
    link: str | None = None
    color: ButtonColor | None = None


RawKeyboard = list[list[VKButton]]


class Keyboard(Actionable, Whenable):
    def __init__(self, id: str | None = None, when: WhenCondition = None) -> None:
        Actionable.__init__(self, id)
        Whenable.__init__(self, when)

    async def render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        if not self.is_(data, manager):
            return []
        return await self._render_keyboard(data, manager)

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        raise NotImplementedError

    async def process_callback(self, callback_data: str, manager: Any) -> bool:
        if self.widget_id is not None and callback_data == self.widget_id:
            return await self._process_own_callback(manager)
        prefix = f"{self.widget_id}:"
        if self.widget_id is not None and callback_data.startswith(prefix):
            return await self._process_item_callback(callback_data[len(prefix):], manager)
        return await self._process_other_callback(callback_data, manager)

    async def _process_own_callback(self, manager: Any) -> bool:
        return False

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        return False

    async def _process_other_callback(self, callback_data: str, manager: Any) -> bool:
        return False

    def __or__(self, other: Keyboard) -> Or:
        return Or(self, other)


class Or(Keyboard):
    def __init__(self, *kbds: Keyboard, when: WhenCondition = None) -> None:
        super().__init__(None, when)
        self._kbds = kbds

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        for kbd in self._kbds:
            rendered = await kbd.render_keyboard(data, manager)
            if rendered:
                return rendered
        return []

    async def _process_other_callback(self, callback_data: str, manager: Any) -> bool:
        for kbd in self._kbds:
            if await kbd.process_callback(callback_data, manager):
                return True
        return False

    def find(self, widget_id: str) -> Any:
        for kbd in self._kbds:
            found = kbd.find(widget_id)
            if found:
                return found
        return None
