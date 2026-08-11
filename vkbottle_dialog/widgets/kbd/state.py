from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...api.entities import ShowMode, StartMode
from ...fsm import State
from ..common import WhenCondition
from ..text.base import Const, Text
from .base import ButtonColor
from .button import Button

_DEFAULT_NEXT_TEXT = Const("▶")
_DEFAULT_BACK_TEXT = Const("◀")
_DEFAULT_CANCEL_TEXT = Const("Отмена")


class SwitchTo(Button):
    def __init__(self, text: Text, id: str, state: State,
                 on_click: Callable | None = None, color: ButtonColor | None = None,
                 show_mode: ShowMode | None = None, when: WhenCondition = None) -> None:
        super().__init__(text, id, on_click, color, None, show_mode, when)
        self._state = state

    async def _action(self, manager: Any) -> None:
        await manager.switch_to(self._state, show_mode=self._show_mode)


class Next(Button):
    def __init__(self, text: Text | None = None, id: str = "__next__", **kwargs) -> None:
        super().__init__(text or _DEFAULT_NEXT_TEXT, id, **kwargs)

    async def _action(self, manager: Any) -> None:
        await manager.next(show_mode=self._show_mode)


class Back(Button):
    def __init__(self, text: Text | None = None, id: str = "__back__", **kwargs) -> None:
        super().__init__(text or _DEFAULT_BACK_TEXT, id, **kwargs)

    async def _action(self, manager: Any) -> None:
        await manager.back(show_mode=self._show_mode)


class Cancel(Button):
    def __init__(self, text: Text | None = None, id: str = "__cancel__",
                 result: Any = None, **kwargs) -> None:
        super().__init__(text or _DEFAULT_CANCEL_TEXT, id, **kwargs)
        self._result = result

    async def _action(self, manager: Any) -> None:
        await manager.done(self._result, show_mode=self._show_mode)


class Start(Button):
    def __init__(self, text: Text, id: str, state: State, data: Any = None,
                 mode: StartMode = StartMode.NORMAL, **kwargs) -> None:
        super().__init__(text, id, **kwargs)
        self._state = state
        self._data = data
        self._mode = mode

    async def _action(self, manager: Any) -> None:
        await manager.start(self._state, data=self._data, mode=self._mode,
                            show_mode=self._show_mode)
