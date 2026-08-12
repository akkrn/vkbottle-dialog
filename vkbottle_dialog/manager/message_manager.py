from __future__ import annotations

import logging
import secrets
from typing import Any

from vkbottle.exception_factory import VKAPIError

from ..api.entities import KeyboardKind, NewMessage, ShowMode, Stack
from ..limits import EDIT_WINDOW_SECONDS
from ..widgets.markup import EMPTY_KEYBOARD_JSON

logger = logging.getLogger("vkbottle_dialog")


class MessageManager:
    def __init__(self, api: Any) -> None:
        self._api = api

    async def show_message(
        self, new: NewMessage, stack: Stack, *, trigger: str, now: float
    ) -> None:
        mode: ShowMode | None = new.show_mode
        if mode == ShowMode.AUTO:
            mode = self._auto_mode(new, stack, trigger, now)
            if mode is None:
                return  # рендер не изменился — пропуск
        if mode == ShowMode.EDIT:
            await self._edit_or_send(new, stack, now)
        elif mode == ShowMode.SEND:
            await self._strip_old_kbd(stack, new.peer_id, now)
            await self._send(new, stack, now)
        elif mode == ShowMode.DELETE_AND_SEND:
            await self._delete_old(stack, new.peer_id)
            await self._send(new, stack, now)

    def _auto_mode(
        self, new: NewMessage, stack: Stack, trigger: str, now: float
    ) -> ShowMode | None:
        # Нормативный порядок ветвления — спека §6.
        if stack.last_cmid is None:
            return ShowMode.SEND
        if stack.last_keyboard_kind is KeyboardKind.TEXT:
            return ShowMode.DELETE_AND_SEND
        if trigger == "message_new":
            return ShowMode.SEND
        # callback / bg:
        if stack.last_render_hash == new.render_hash():
            return None
        if self._editable(stack, now):
            return ShowMode.EDIT
        return ShowMode.SEND

    def _editable(self, stack: Stack, now: float) -> bool:
        return (
            stack.last_cmid is not None
            and stack.last_message_sent_at is not None
            and now - stack.last_message_sent_at < EDIT_WINDOW_SECONDS
        )

    async def _edit_or_send(self, new: NewMessage, stack: Stack, now: float) -> None:
        if not self._editable(stack, now):
            await self._send(new, stack, now)
            return
        params: dict = {
            "peer_id": new.peer_id,
            "cmid": stack.last_cmid,
            "message": new.text,
            "disable_mentions": int(new.disable_mentions),
            "dont_parse_links": int(new.dont_parse_links),
        }
        if new.keyboard is not None:
            params["keyboard"] = new.keyboard  # всегда с клавиатурой — иначе VK сотрёт
        try:
            await self._api.request("messages.edit", params)
        except VKAPIError as e:
            logger.debug("edit failed (%s), отправляю новое окно", e)
            await self._send(new, stack, now)
            return
        stack.last_render_hash = new.render_hash()
        stack.last_keyboard_kind = new.keyboard_kind
        stack.last_text = new.text

    async def _send(self, new: NewMessage, stack: Stack, now: float) -> None:
        params: dict = {
            "peer_ids": [new.peer_id],
            "random_id": secrets.randbelow(2**31),
            "message": new.text,
            "disable_mentions": int(new.disable_mentions),
            "dont_parse_links": int(new.dont_parse_links),
        }
        if new.keyboard is not None:
            params["keyboard"] = new.keyboard
        if new.attachments:
            params["attachment"] = ",".join(new.attachments)
        response = await self._api.request("messages.send", params)
        item = response["response"][0]
        stack.last_cmid = item["conversation_message_id"]
        stack.last_message_sent_at = now
        stack.last_keyboard_kind = new.keyboard_kind
        stack.last_render_hash = new.render_hash()
        stack.last_text = new.text

    async def _strip_old_kbd(self, stack: Stack, peer_id: int, now: float) -> None:
        if stack.last_keyboard_kind is not KeyboardKind.INLINE or not self._editable(stack, now):
            return
        try:
            await self._api.request(
                "messages.edit",
                {
                    "peer_id": peer_id,
                    "cmid": stack.last_cmid,
                    "message": stack.last_text or " ",  # старый текст сохраняем
                },
            )
        except VKAPIError as e:
            logger.debug("strip kbd failed: %s", e)

    async def _delete_old(self, stack: Stack, peer_id: int) -> None:
        if stack.last_cmid is None:
            return
        try:
            await self._api.request(
                "messages.delete",
                {
                    "peer_id": peer_id,
                    "cmids": [stack.last_cmid],
                    "delete_for_all": 1,
                },
            )
        except VKAPIError as e:
            logger.debug("delete failed: %s — окно останется мёртвым", e)

    async def remove_kbd(self, stack: Stack, peer_id: int, *, now: float) -> None:
        if stack.last_keyboard_kind is KeyboardKind.INLINE and self._editable(stack, now):
            try:
                await self._api.request(
                    "messages.edit",
                    {
                        "peer_id": peer_id,
                        "cmid": stack.last_cmid,
                        "message": stack.last_text or " ",
                    },
                )
            except VKAPIError as e:
                logger.debug("remove_kbd failed: %s", e)
        elif stack.last_keyboard_kind is KeyboardKind.TEXT:
            await self._api.request(
                "messages.send",
                {
                    "peer_ids": [peer_id],
                    "random_id": secrets.randbelow(2**31),
                    "message": "✓",
                    "keyboard": EMPTY_KEYBOARD_JSON,
                },
            )
        stack.clear_message()
