from __future__ import annotations

import json
import logging
import secrets
from typing import Any

from vkbottle.exception_factory import VKAPIError

from ..api.entities import CarouselSpec, KeyboardKind, NewMessage, ShowMode, Stack
from ..limits import EDIT_WINDOW_SECONDS, LABEL_MAX
from ..widgets.markup import EMPTY_KEYBOARD_JSON
from .media_resolver import attachment_to_photo_id

logger = logging.getLogger("vkbottle_dialog")


def _carousel_label(button: Any) -> str:
    label = button.label or " "
    return label[: LABEL_MAX - 1] + "…" if len(label) > LABEL_MAX else label


def _carousel_button_doc(button: Any) -> dict:
    if button.action == "open_link":
        return {
            "action": {"type": "open_link", "link": button.link, "label": _carousel_label(button)}
        }
    doc: dict = {
        "action": {
            "type": "callback",
            "label": _carousel_label(button),
            "payload": button.callback_data,
        }
    }
    if button.color is not None:
        doc["color"] = button.color.value
    return doc


class MessageManager:
    def __init__(self, api: Any, media_resolver: Any = None) -> None:
        self._api = api
        self._media_resolver = media_resolver

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
        if (new.carousel is not None) != stack.last_had_carousel:
            # Карусель<->обычное окно: omit-семантика template в messages.edit
            # не подтверждена смоуком (спека §5.2) — консервативно всегда
            # удаляем старое сообщение и шлём новое.
            return ShowMode.DELETE_AND_SEND
        if stack.last_keyboard_kind is KeyboardKind.TEXT:
            # Callback-кнопки нижней клавиатуры шлют message_event без
            # смены самой клавиатуры (она общая на беседу/ЛС и уже стоит
            # на устройстве) — редактируем только текст окна, не пересылаем.
            if (
                trigger == "message_event"
                and new.keyboard_kind is KeyboardKind.TEXT
                and stack.last_kb_hash == new.kb_hash()
                and self._editable(stack, now)
            ):
                return ShowMode.EDIT
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

    async def _resolve_media(self, new: NewMessage) -> tuple[str | None, bool]:
        """(attachment | None, failed) — None+False когда медиа нет."""
        if new.media is None or self._media_resolver is None:
            return None, False
        attachment = await self._media_resolver.resolve(new.media, new.peer_id)
        return attachment, attachment is None

    async def _resolve_carousel(self, new: NewMessage) -> tuple[str | None, bool]:
        """(template JSON | None, failed) — собирает VK carousel-template из
        CarouselSpec: photo резолвится через тот же MediaResolver, что и
        обычное медиа окна (attachment -> photo_id хелпером
        attachment_to_photo_id). failed=True только если попытка резолва
        ДЕЙСТВИТЕЛЬНО провалилась (resolve() вернул None) — нет резолвера
        это конфигурационный выбор, а не сбой (симметрично _resolve_media);
        элемент уйдёт без photo_id — деградация как у обычного медиа,
        насколько это ломает VK-требование структурной униформности
        карусели — smoke §7."""
        spec: CarouselSpec | None = new.carousel
        if spec is None:
            return None, False
        failed = False
        elements: list[dict] = []
        for element in spec.elements:
            doc: dict = {"title": element.title, "description": element.description}
            if element.photo is not None and self._media_resolver is not None:
                attachment = await self._media_resolver.resolve(element.photo, new.peer_id)
                if attachment is not None:
                    doc["photo_id"] = attachment_to_photo_id(attachment)
                else:
                    failed = True
            if element.buttons:
                doc["buttons"] = [_carousel_button_doc(b) for b in element.buttons]
            if element.action is not None:
                doc["action"] = element.action
            elements.append(doc)
        template = json.dumps(
            {"type": "carousel", "elements": elements}, ensure_ascii=False, separators=(",", ":")
        )
        return template, failed

    async def _edit_or_send(self, new: NewMessage, stack: Stack, now: float) -> None:
        if not self._editable(stack, now):
            await self._send(new, stack, now)
            return
        if (new.carousel is not None) != stack.last_had_carousel:
            # Явный ShowMode.EDIT (в обход AUTO) на границе карусель<->окно —
            # omit-семантика template в messages.edit не подтверждена (спека
            # §5.2/§7): консервативно ведём себя как AUTO — delete+send.
            await self._delete_old(stack, new.peer_id)
            await self._send(new, stack, now)
            return
        params: dict = {
            "peer_id": new.peer_id,
            "cmid": stack.last_cmid,
            "message": new.text,
            "disable_mentions": int(new.disable_mentions),
            "dont_parse_links": int(new.dont_parse_links),
        }
        # Нижняя (TEXT) клавиатура не редактируется через messages.edit — она
        # общая на переписку и уже стоит на устройстве; передаём её здесь
        # только когда она ставится ВПЕРВЫЕ этим редактированием (переход
        # с другого вида клавиатуры) или ИЗМЕНИЛАСЬ (иначе новая клавиатура
        # никогда не применится), а не когда она и так уже TEXT и не менялась.
        skip_keyboard = (
            new.keyboard_kind is KeyboardKind.TEXT
            and stack.last_keyboard_kind is KeyboardKind.TEXT
            and stack.last_kb_hash == new.kb_hash()
        )
        if new.keyboard is not None and not skip_keyboard:
            params["keyboard"] = new.keyboard  # всегда с клавиатурой — иначе VK сотрёт
        attachment, failed = await self._resolve_media(new)
        if attachment is not None:
            params["attachment"] = attachment
        elif new.media is None and stack.last_media_key:
            params["attachment"] = ""  # явная очистка — омит не очищает вложение
        template, carousel_failed = await self._resolve_carousel(new)
        if template is not None:
            params["template"] = template
        try:
            await self._api.request("messages.edit", params)
        except VKAPIError as e:
            logger.warning(
                "messages.edit не прошёл (code=%s: %s; params=%s) — "
                "отправляю новое окно вместо редактирования",
                getattr(e, "code", "?"),
                e,
                sorted(params),
            )
            await self._send(new, stack, now)
            return
        stack.last_render_hash = new.render_hash(
            "media:failed" if failed else None, "carousel:failed" if carousel_failed else None
        )
        stack.last_keyboard_kind = new.keyboard_kind
        stack.last_kb_hash = new.kb_hash()
        stack.last_text = new.text
        stack.last_had_carousel = new.carousel is not None
        stack.last_media_key = (
            new.media.source_key()
            if attachment is not None and new.media
            else (None if new.media is None else stack.last_media_key)
        )

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
        attachment, failed = await self._resolve_media(new)
        if attachment is not None:
            params["attachment"] = attachment
        template, carousel_failed = await self._resolve_carousel(new)
        if template is not None:
            params["template"] = template
        response = await self._api.request("messages.send", params)
        item = response["response"][0]
        stack.last_cmid = item["conversation_message_id"]
        stack.last_message_sent_at = now
        stack.last_keyboard_kind = new.keyboard_kind
        stack.last_render_hash = new.render_hash(
            "media:failed" if failed else None, "carousel:failed" if carousel_failed else None
        )
        stack.last_kb_hash = new.kb_hash()
        stack.last_text = new.text
        stack.last_had_carousel = new.carousel is not None
        stack.last_media_key = (
            new.media.source_key() if attachment is not None and new.media else None
        )

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
