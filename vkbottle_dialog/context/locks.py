from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar

# Ключи, удерживаемые текущей логической задачей (спека §4: реентерабельность).
_held_keys: ContextVar[frozenset[str]] = ContextVar("vkd_held_keys", default=frozenset())


class LockRegistry:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._waiters: dict[str, int] = {}

    @asynccontextmanager
    async def acquire(self, key: str):
        held = _held_keys.get()
        if key in held:
            yield  # реентерабельный вход — lock уже наш
            return
        lock = self._locks.setdefault(key, asyncio.Lock())
        self._waiters[key] = self._waiters.get(key, 0) + 1
        try:
            async with lock:
                token = _held_keys.set(held | {key})
                try:
                    yield
                finally:
                    _held_keys.reset(token)
        finally:
            self._waiters[key] -= 1
            if self._waiters[key] == 0:
                self._waiters.pop(key, None)
                self._locks.pop(key, None)
