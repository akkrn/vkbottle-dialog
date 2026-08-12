from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .api.entities import LaunchMode, NewMessage
from .exceptions import DialogConfigError, UnknownState
from .fsm import State, StatesGroup
from .widgets.common import ensure_data_getter, ensure_event_processor
from .window import Window


class Dialog:
    def __init__(
        self,
        *windows: Window,
        on_start: Callable | None = None,
        on_close: Callable | None = None,
        on_process_result: Callable | None = None,
        launch_mode: LaunchMode = LaunchMode.STANDARD,
        getter: Any = None,
    ) -> None:
        if not windows:
            raise DialogConfigError("Dialog требует хотя бы одно окно")
        groups = {w.state.group for w in windows}
        if len(groups) != 1:
            raise DialogConfigError(f"окна из разных StatesGroup: {groups}")
        states = [w.state for w in windows]
        if len(set(states)) != len(states):
            raise DialogConfigError("дубликаты состояний в окнах")
        self._windows: dict[State, Window] = {w.state: w for w in windows}
        self._states = tuple(states)
        self.launch_mode = launch_mode
        self._on_start = ensure_event_processor(on_start)
        self._on_close = ensure_event_processor(on_close)
        self._on_process_result = ensure_event_processor(on_process_result)
        self._getter = ensure_data_getter(getter)

    def states_group(self) -> type[StatesGroup]:
        return self._states[0].group

    def states(self) -> tuple[State, ...]:
        return self._states

    def window_for(self, state: State) -> Window:
        try:
            return self._windows[state]
        except KeyError:
            raise UnknownState(f"нет окна для {state.state}") from None

    async def load_data(self, manager: Any) -> dict:
        data = await manager.load_data()
        kwargs = {**getattr(manager, "middleware_data", {}), "dialog_manager": manager}
        data.update(await self._getter(**kwargs))
        return data

    async def render(
        self,
        manager: Any,
        event_ctx: Any,
        intent_id: str,
        secret: str | None,
        default_markup_factory: Any,
    ) -> NewMessage:
        window = self.window_for(manager.current_context().state)
        return await window.render(manager, event_ctx, intent_id, secret, default_markup_factory)

    async def process_callback(self, callback_data: str, manager: Any) -> bool:
        window = self.window_for(manager.current_context().state)
        return await window.process_callback(callback_data, manager)

    async def process_message(self, message: Any, manager: Any) -> bool:
        window = self.window_for(manager.current_context().state)
        return await window.process_message(message, manager)

    async def process_start(
        self, manager: Any, start_data: Any, state: State | None = None
    ) -> None:
        await manager.switch_to(state or self._states[0])
        await self._on_start.process_event(start_data, manager)

    async def process_close(self, result: Any, manager: Any) -> None:
        await self._on_close.process_event(result, manager)

    async def process_result(self, start_data: Any, result: Any, manager: Any) -> None:
        await self._on_process_result.process_event(start_data, result, manager)

    async def process_window_result(self, start_data: Any, result: Any, manager: Any) -> None:
        window = self.window_for(manager.current_context().state)
        await window.process_result(start_data, result, manager)

    def find(self, widget_id: str) -> Any:
        for window in self._windows.values():
            found = window.find(widget_id)
            if found:
                return found
        return None

    def find_scroll(self, widget_id: str) -> Any:
        for window in self._windows.values():
            found = window.find_scroll(widget_id)
            if found:
                return found
        return None
