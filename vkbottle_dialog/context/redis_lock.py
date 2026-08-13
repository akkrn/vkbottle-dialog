from __future__ import annotations

import asyncio
import contextlib
import random
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from .locks import LockRegistry

# продлеваем TTL только если ключ всё ещё содержит НАШ токен
_RENEW_SCRIPT = (
    'if redis.call("get",KEYS[1])==ARGV[1] then '
    'return redis.call("pexpire",KEYS[1],ARGV[2]) else return 0 end'
)
# снимаем lock только если ключ всё ещё содержит НАШ токен (чужой не трогаем)
_RELEASE_SCRIPT = (
    'if redis.call("get",KEYS[1])==ARGV[1] then return redis.call("del",KEYS[1]) else return 0 end'
)


class RedisLockRegistry:
    """Двухслойный distributed lock для мульти-инстанс развёртывания.

    Сначала берётся внутрипроцессный LockRegistry.acquire (реентерабельность в
    рамках одной asyncio-задачи + сериализация задач одного процесса), затем —
    redis `SET vkd:lock:{key} {token} NX PX {ttl_ms}` с retry-джиттером
    (сериализация между инстансами).

    Пока redis-lock удерживается, фоновая задача-heartbeat каждые ttl/3 секунд
    продлевает TTL (Lua compare-and-pexpire по токену) — это защищает долгие
    критические секции (например загрузку медиа дольше ttl) от истечения TTL
    без освобождения lock'а под активным хендлером. Критическая секция ядра
    остаётся непрерывной и атомарной — heartbeat её не меняет.
    """

    def __init__(
        self,
        redis: Any,
        ttl: float = 30.0,
        retry_interval: float = 0.05,
        jitter: float = 0.5,
    ) -> None:
        self._redis = redis
        self._ttl = ttl
        self._retry_interval = retry_interval
        self._jitter = jitter
        self._locks = LockRegistry()

    def _redis_key(self, key: str) -> str:
        return f"vkd:lock:{key}"

    @asynccontextmanager
    async def acquire(self, key: str) -> AsyncIterator[None]:
        reentrant = self._locks.is_held_by_current_task(key)
        async with self._locks.acquire(key):
            if reentrant:
                # lock уже наш (в рамках этой asyncio-задачи) — redis не трогаем,
                # второй heartbeat не запускаем, просто проходим сквозь
                yield
                return
            token = secrets.token_hex()
            rkey = self._redis_key(key)
            await self._acquire_redis(rkey, token)
            heartbeat = asyncio.create_task(self._heartbeat(rkey, token))
            try:
                yield
            finally:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat
                await self._redis.eval(_RELEASE_SCRIPT, 1, rkey, token)

    async def _acquire_redis(self, rkey: str, token: str) -> None:
        px = int(self._ttl * 1000)
        while True:
            ok = await self._redis.set(rkey, token, nx=True, px=px)
            if ok:
                return
            delay = random.uniform(1 - self._jitter, 1 + self._jitter) * self._retry_interval
            await asyncio.sleep(delay)

    async def _heartbeat(self, rkey: str, token: str) -> None:
        px = int(self._ttl * 1000)
        interval = self._ttl / 3
        while True:
            await asyncio.sleep(interval)
            await self._redis.eval(_RENEW_SCRIPT, 1, rkey, token, px)


__all__ = ["RedisLockRegistry"]
