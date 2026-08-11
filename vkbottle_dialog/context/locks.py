from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


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

    @asynccontextmanager
    async def acquire(self, key: str):
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
