from __future__ import annotations

import copy


class MemoryStorage:
    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    async def get(self, key: str) -> dict | None:
        value = self._data.get(key)
        return copy.deepcopy(value) if value is not None else None

    async def set(self, key: str, data: dict) -> None:
        self._data[key] = copy.deepcopy(data)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def touch(self, *keys: str) -> None:
        pass
