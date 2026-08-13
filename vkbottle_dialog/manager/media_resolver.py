from __future__ import annotations

import contextlib
import hashlib
import logging
import os
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from vkbottle.tools import DocMessagesUploader, PhotoMessageUploader

from ..api.entities import MediaAttachment
from ..api.protocols import BaseStorage
from ..context.locks import LockRegistry

logger = logging.getLogger("vkbottle_dialog")

MEDIA_CACHE_MAXSIZE = 1024


class MediaResolver:
    def __init__(
        self,
        api: Any,
        storage: BaseStorage | None = None,
        photo_uploader_factory: Callable | None = None,
        doc_uploader_factory: Callable | None = None,
    ) -> None:
        self._api = api
        self._storage = storage
        self._photo_factory = photo_uploader_factory or PhotoMessageUploader
        self._doc_factory = doc_uploader_factory or DocMessagesUploader
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._locks = LockRegistry()

    def _cache_key(self, media: MediaAttachment, peer_id: int) -> str:
        key = media.source_key()
        if media.path:
            with contextlib.suppress(OSError):
                key += f"|{os.path.getmtime(media.path)}"
        if media.type == "doc":
            # переиспользуемость документов между peer не гарантирована
            key += f"|peer:{peer_id}"
        return key

    async def resolve(self, media: MediaAttachment, peer_id: int) -> str | None:
        if media.attachment:
            return media.attachment
        key = self._cache_key(media, peer_id)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        async with self._locks.acquire(key):
            # второй конкурентный resolve того же ключа мог дождаться lock'а
            # и найти значение уже в кэше — не грузим повторно
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            stored = await self._storage_get(key)
            if stored:
                self._cache_put(key, stored)
                return stored
            try:
                attachment = await self._upload(media, peer_id)
            except Exception as e:  # деградация: окно уйдёт без медиа
                logger.warning("media upload failed for %s: %r", media.source_key(), e)
                return None
            self._cache_put(key, attachment)
            await self._storage_set(key, attachment)
            return attachment

    def _cache_put(self, key: str, attachment: str) -> None:
        self._cache[key] = attachment
        self._cache.move_to_end(key)
        if len(self._cache) > MEDIA_CACHE_MAXSIZE:
            self._cache.popitem(last=False)

    async def _upload(self, media: MediaAttachment, peer_id: int) -> str:
        source: Any = media.path
        title = media.title
        if media.url:
            source = await self._api.http_client.request_content(media.url)
            if title is None:
                title = os.path.basename(media.url.split("?")[0]) or None
        elif media.path and title is None:
            title = os.path.basename(media.path)
        if media.type == "doc":
            uploader = self._doc_factory(self._api)
            return await uploader.upload(source, peer_id=peer_id, title=title)
        uploader = self._photo_factory(self._api)
        return await uploader.upload(source, peer_id=peer_id)

    async def _storage_get(self, key: str) -> str | None:
        if self._storage is None:
            return None
        try:
            doc = await self._storage.get(self._storage_key(key))
            return doc.get("attachment") if doc else None
        except Exception as e:
            logger.warning("media cache storage get failed: %r", e)
            return None

    async def _storage_set(self, key: str, attachment: str) -> None:
        if self._storage is None:
            return
        try:
            await self._storage.set(self._storage_key(key), {"attachment": attachment})
        except Exception as e:
            logger.warning("media cache storage set failed: %r", e)

    @staticmethod
    def _storage_key(key: str) -> str:
        return f"vkd:media:{hashlib.sha1(key.encode()).hexdigest()}"
