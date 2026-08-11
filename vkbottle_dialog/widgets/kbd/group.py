from __future__ import annotations

from typing import Any

from ..common import WhenCondition
from .base import Keyboard, RawKeyboard


class Group(Keyboard):
    def __init__(self, *kbds: Keyboard, width: int | None = None,
                 id: str | None = None, when: WhenCondition = None) -> None:
        super().__init__(id, when)
        self._kbds = kbds
        self._width = width

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        kbd: RawKeyboard = []
        for child in self._kbds:
            kbd.extend(await child.render_keyboard(data, manager))
        if self._width is None:
            return [row for row in kbd if row]
        result: RawKeyboard = [[]]
        for button in (b for row in kbd for b in row):
            if len(result[-1]) >= self._width:
                result.append([])
            result[-1].append(button)
        return [row for row in result if row]

    async def _process_other_callback(self, callback_data: str, manager: Any) -> bool:
        for child in self._kbds:
            if await child.process_callback(callback_data, manager):
                return True
        return False

    def find(self, widget_id: str) -> Any:
        if self.widget_id == widget_id:
            return self
        for child in self._kbds:
            found = child.find(widget_id)
            if found:
                return found
        return None


class Row(Group):
    def __init__(self, *kbds: Keyboard, id: str | None = None,
                 when: WhenCondition = None) -> None:
        super().__init__(*kbds, width=9999, id=id, when=when)


class Column(Group):
    def __init__(self, *kbds: Keyboard, id: str | None = None,
                 when: WhenCondition = None) -> None:
        super().__init__(*kbds, width=1, id=id, when=when)
