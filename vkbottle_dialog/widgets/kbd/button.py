from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...api.entities import ShowMode
from ..common import WhenCondition, ensure_event_processor
from ..text.base import Text
from .base import ButtonColor, Keyboard, RawKeyboard, VKButton


class Button(Keyboard):
    def __init__(self, text: Text, id: str, on_click: Callable | None = None,
                 color: ButtonColor | None = None, snackbar: str | None = None,
                 show_mode: ShowMode | None = None, when: WhenCondition = None) -> None:
        super().__init__(id, when)
        self._text = text
        self._on_click = ensure_event_processor(on_click)
        self._color = color
        self._snackbar = snackbar
        self._show_mode = show_mode

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        label = await self._text.render_text(data, manager)
        return [[VKButton(action="callback", label=label,
                          callback_data=self.widget_id, color=self._color)]]

    async def _process_own_callback(self, manager: Any) -> bool:
        if self._snackbar is not None:
            await manager.answer(snackbar=self._snackbar)
        if self._show_mode is not None:
            manager.show_mode = self._show_mode
        await self._on_click.process_event(manager.event, self, manager)
        await self._action(manager)
        return True

    async def _action(self, manager: Any) -> None:
        pass


class Url(Keyboard):
    def __init__(self, text: Text, url: Text, id: str | None = None,
                 when: WhenCondition = None) -> None:
        super().__init__(id, when)
        self._text = text
        self._url = url

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        return [[VKButton(action="open_link",
                          label=await self._text.render_text(data, manager),
                          callback_data=None,
                          link=await self._url.render_text(data, manager))]]
