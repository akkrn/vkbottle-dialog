from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol, runtime_checkable


@runtime_checkable
class LockRegistryLike(Protocol):
    """Структурный интерфейс, которому удовлетворяют LockRegistry (single-instance,
    дефолт) и RedisLockRegistry (context/redis_lock.py, мульти-инстанс)."""

    def acquire(self, key: str) -> AbstractAsyncContextManager[None]: ...


class LockRegistry:
    """Per-key взаимное исключение с реентерабельностью в рамках одной asyncio-задачи.

    Реентерабельность определяется по identity текущего asyncio.Task —
    задача, порождённая create_task/ensure_future внутри критической секции,
    честно ждёт lock (наследования "held"-состояния нет).
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._waiters: dict[str, int] = {}
        self._owners: dict[str, asyncio.Task] = {}

    def is_held_by_current_task(self, key: str) -> bool:
        """True, если текущая asyncio-задача уже держит lock на key — следующий
        acquire(key) пройдёт реентерабельно, без нового захвата."""
        return self._owners.get(key) is asyncio.current_task()

    @asynccontextmanager
    async def acquire(self, key: str) -> AsyncIterator[None]:
        current = asyncio.current_task()
        assert current is not None, "LockRegistry.acquire вне asyncio-задачи"
        if self._owners.get(key) is current:
            yield  # реентерабельный вход — lock уже наш
            return
        lock = self._locks.setdefault(key, asyncio.Lock())
        self._waiters[key] = self._waiters.get(key, 0) + 1
        try:
            async with lock:
                self._owners[key] = current
                try:
                    yield
                finally:
                    del self._owners[key]
        finally:
            self._waiters[key] -= 1
            if self._waiters[key] == 0:
                self._waiters.pop(key, None)
                self._locks.pop(key, None)
