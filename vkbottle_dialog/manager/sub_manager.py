from __future__ import annotations

import dataclasses
from typing import Any

from ..api.entities import Context, ShowMode, Stack, StartMode
from .manager import DialogConfig


class SubManager:
    """Manager, привязанный к одной строке (item_id) виджета widget_id —
    так один и тот же виджет, отрисованный много раз в списке/скролле,
    хранит get/set_widget_data отдельно на каждую строку. current_context()
    подменяет widget_data на row-словарь; вся остальная поверхность —
    делегация в родительский manager (порт aiogram_dialog.SubManager)."""

    def __init__(
        self,
        widget: Any,
        manager: Any,
        widget_id: str,
        item_id: str,
    ) -> None:
        self.widget = widget
        self.manager = manager
        self.widget_id = widget_id
        self.item_id = item_id

    @property
    def event(self) -> Any:
        return self.manager.event

    @property
    def middleware_data(self) -> dict:
        return self.manager.middleware_data

    @property
    def dialog_data(self) -> dict:
        return self.current_context().dialog_data

    @property
    def start_data(self) -> Any:
        return self.manager.start_data

    @property
    def jinja_env(self) -> Any:
        return self.manager.jinja_env

    @property
    def config(self) -> DialogConfig:
        return self.manager.config

    def current_context(self) -> Context:
        context = self.manager.current_context()
        data = context.widget_data.setdefault(self.widget_id, {})
        row_data = data.setdefault(self.item_id, {})
        return dataclasses.replace(context, widget_data=row_data)

    def has_context(self) -> bool:
        return self.manager.has_context()

    def current_stack(self) -> Stack:
        return self.manager.current_stack()

    async def load_data(self) -> dict:
        return await self.manager.load_data()

    def find(self, widget_id: str) -> Any:
        widget = self.widget.find(widget_id)
        if widget is None:
            return None
        return widget.managed(self)

    def find_in_parent(self, widget_id: str) -> Any:
        return self.manager.find(widget_id)

    def find_scroll(self, widget_id: str) -> Any:
        return self.manager.find_scroll(widget_id)

    @property
    def show_mode(self) -> ShowMode:
        return self.manager.show_mode

    @show_mode.setter
    def show_mode(self, show_mode: ShowMode) -> None:
        self.manager.show_mode = show_mode

    async def show(self) -> None:
        await self.manager.show()

    async def answer(self, snackbar: str | None = None, open_link: str | None = None) -> None:
        await self.manager.answer(snackbar=snackbar, open_link=open_link)

    async def next(self, show_mode: ShowMode | None = None) -> None:
        await self.manager.next(show_mode)

    async def back(self, show_mode: ShowMode | None = None) -> None:
        await self.manager.back(show_mode)

    async def done(self, result: Any = None, show_mode: ShowMode | None = None) -> None:
        await self.manager.done(result, show_mode)

    async def start(
        self,
        state: Any,
        data: Any = None,
        mode: StartMode = StartMode.NORMAL,
        show_mode: ShowMode | None = None,
    ) -> None:
        await self.manager.start(state, data=data, mode=mode, show_mode=show_mode)

    async def switch_to(self, state: Any, show_mode: ShowMode | None = None) -> None:
        await self.manager.switch_to(state, show_mode)

    async def update(self, data: dict | None = None, show_mode: ShowMode | None = None) -> None:
        if data:
            self.current_context().dialog_data.update(data)
        if show_mode is not None:
            self.show_mode = show_mode
        await self.show()

    def bg(self, peer_id: int | None = None, user_id: int | None = None) -> Any:
        return self.manager.bg(peer_id=peer_id, user_id=user_id)
