from __future__ import annotations

import json
from typing import Any

DEFAULT_TTL = 30 * 24 * 3600


class RedisStorage:
    def __init__(self, redis: Any, ttl: int = DEFAULT_TTL, prefix: str = "") -> None:
        self._redis = redis
        self._ttl = ttl
        self._prefix = prefix

    def _k(self, key: str) -> str:
        return self._prefix + key

    async def get(self, key: str) -> dict | None:
        raw = await self._redis.get(self._k(key))
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, data: dict) -> None:
        await self._redis.set(self._k(key), json.dumps(data, ensure_ascii=False),
                              ex=self._ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(self._k(key))

    async def touch(self, *keys: str) -> None:
        if not keys:
            return
        pipe = self._redis.pipeline()
        for key in keys:
            pipe.expire(self._k(key), self._ttl)
        await pipe.execute()
