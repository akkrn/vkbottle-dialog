from __future__ import annotations

from typing import Any

from ..api.entities import MediaAttachment
from .common import Whenable, WhenCondition
from .text.base import Const, Text


class Media(Whenable):
    async def render_media(self, data: dict, manager: Any) -> MediaAttachment | None:
        if not self.is_(data, manager):
            return None
        return await self._render_media(data, manager)

    async def _render_media(self, data: dict, manager: Any) -> MediaAttachment | None:
        raise NotImplementedError

    def find(self, widget_id: str) -> Any:
        return None


def _ensure_text(value: Text | str | None) -> Text | None:
    if value is None:
        return None
    return Const(value) if isinstance(value, str) else value


class StaticMedia(Media):
    def __init__(
        self,
        path: Text | str | None = None,
        url: Text | str | None = None,
        type: str = "photo",
        title: str | None = None,
        when: WhenCondition = None,
    ) -> None:
        super().__init__(when)
        self._path = _ensure_text(path)
        self._url = _ensure_text(url)
        self._type = type
        self._title = title

    async def _render_media(self, data: dict, manager: Any) -> MediaAttachment | None:
        path = await self._path.render_text(data, manager) if self._path else None
        url = await self._url.render_text(data, manager) if self._url else None
        if not path and not url:
            return None
        return MediaAttachment(
            type=self._type, path=path or None, url=url or None, title=self._title
        )
