from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .common import Actionable, ensure_event_processor


class BaseInput(Actionable):
    async def process_message(self, message: Any, manager: Any) -> bool:
        raise NotImplementedError


class MessageInput(BaseInput):
    def __init__(
        self,
        func: Callable,
        content_types: list[str] | None = None,
        filter: Callable | None = None,
    ) -> None:
        super().__init__(None)
        self._func = ensure_event_processor(func)
        self._content_types = content_types
        self._filter = filter

    def _matches(self, message: Any) -> bool:
        if self._filter is not None and not self._filter(message):
            return False
        if self._content_types is None:
            return True
        types = {a.type for a in message.attachments} or {"text"}
        return bool(types & set(self._content_types))

    async def process_message(self, message: Any, manager: Any) -> bool:
        if not self._matches(message):
            return False
        await self._func.process_event(message, self, manager)
        return True


class TextInput(BaseInput):
    def __init__(
        self,
        id: str,
        type_factory: Callable = str,
        on_success: Callable | None = None,
        on_error: Callable | None = None,
        filter: Callable | None = None,
    ) -> None:
        super().__init__(id)
        self._type_factory = type_factory
        self._on_success = ensure_event_processor(on_success)
        self._on_error = on_error
        self._filter = filter

    async def process_message(self, message: Any, manager: Any) -> bool:
        if message.attachments or not message.text:
            return False
        if self._filter is not None and not self._filter(message):
            return False
        try:
            value = self._type_factory(message.text)
        except ValueError as e:
            if self._on_error is None:
                return False
            await self._on_error(message, self, manager, e)
            return True
        self.set_widget_data(manager, message.text)
        await self._on_success.process_event(message, self, manager, value)
        return True

    def managed(self, manager: Any) -> ManagedTextInput:
        return ManagedTextInput(self, manager)


class ManagedTextInput:
    def __init__(self, widget: TextInput, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def get_value(self) -> Any:
        raw = self._widget.get_widget_data(self._manager, None)
        return self._widget._type_factory(raw) if raw is not None else None


class CombinedInput(BaseInput):
    def __init__(self, *inputs: BaseInput) -> None:
        super().__init__(None)
        self._inputs = inputs

    async def process_message(self, message: Any, manager: Any) -> bool:
        for inp in self._inputs:
            if await inp.process_message(message, manager):
                return True
        return False

    def find(self, widget_id: str) -> Any:
        for inp in self._inputs:
            found = inp.find(widget_id)
            if found:
                return found
        return None
