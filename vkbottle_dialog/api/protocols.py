from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .entities import Context, EventContext, Stack


class BaseStorage(Protocol):
    async def get(self, key: str) -> dict | None: ...
    async def set(self, key: str, data: dict) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def touch(self, *keys: str) -> None: ...


class StackAccessValidator(Protocol):
    async def is_allowed(
        self, stack: Stack, context: Context | None, event_ctx: EventContext
    ) -> bool: ...
