from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any

from vkbottle.dispatch.views.abc import ABCView

from ..api.entities import PEER_ID_OFFSET, EventContext
from ..context.locks import LockRegistryLike
from ..context.proxy import StorageProxy
from ..exceptions import (
    CancelEventProcessing,
    DialogError,
    InvalidPayload,
    OutdatedIntent,
    UnknownIntent,
    UnknownState,
)
from ..manager.manager import DialogConfig, ManagerImpl
from ..manager.message_manager import MessageManager
from ..payload import ParsedPayload, decode_payload

logger = logging.getLogger("vkbottle_dialog")


class AnswerLatch:
    """Один ответ на message_event: первый answer() шлёт
    messages.sendMessageEventAnswer, повторные — no-op (False)."""

    def __init__(self, api: Any, event_id: str, user_id: int, peer_id: int) -> None:
        self._api = api
        self._event_id = event_id
        self._user_id = user_id
        self._peer_id = peer_id
        self.answered = False

    async def answer(self, snackbar: str | None = None, open_link: str | None = None) -> bool:
        if self.answered:
            return False
        self.answered = True
        params: dict = {
            "event_id": self._event_id,
            "user_id": self._user_id,
            "peer_id": self._peer_id,
        }
        if snackbar is not None:
            params["event_data"] = json.dumps(
                {"type": "show_snackbar", "text": snackbar}, ensure_ascii=False
            )
        elif open_link is not None:
            params["event_data"] = json.dumps(
                {"type": "open_link", "link": open_link}, ensure_ascii=False
            )
        await self._api.request("messages.sendMessageEventAnswer", params)
        return True


class DialogView(ABCView):
    """Нормативный обработчик message_new/message_event — спека §5.

    Регистрируется НЕ через ``bot.router.add_view`` (не работает: ``Bot.router``
    — property, пересобирающая views из ``labeler.views()`` на каждое событие),
    а обёрткой ``labeler.views`` в ``setup_dialogs``.
    """

    def __init__(
        self,
        *,
        registry: Any,
        proxy: StorageProxy,
        locks: LockRegistryLike,
        config: DialogConfig,
        bg_factory: Any,
        on_unknown_intent: Any = None,
        on_unknown_state: Any = None,
    ) -> None:
        super().__init__()
        self.registry = registry
        self.proxy = proxy
        self.locks = locks
        self.config = config
        self.bg_factory = bg_factory
        self.on_unknown_intent = on_unknown_intent
        self.on_unknown_state = on_unknown_state

    async def process_event(self, event: dict) -> bool:
        return event.get("type") in ("message_new", "message_event")

    async def handle_event(self, event: dict, ctx_api: Any, state_dispenser: Any) -> None:
        kind = event["type"]
        obj = event["object"]
        if kind == "message_new":
            msg = obj["message"]
            peer_id, from_id = msg["peer_id"], msg["from_id"]
            raw_payload = msg.get("payload")
            client_info = obj.get("client_info") or {}
        else:
            peer_id, from_id = obj["peer_id"], obj["user_id"]
            raw_payload = obj.get("payload")
            client_info = {}
        owner_id = from_id if peer_id >= PEER_ID_OFFSET else peer_id
        ev = EventContext(
            group_id=event.get("group_id", 0),
            peer_id=peer_id,
            owner_id=owner_id,
            user_id=from_id,
            kind=kind,
            raw=obj,
        )
        self.bg_factory.set_group_id(ev.group_id)

        latch = None
        if kind == "message_event":
            latch = AnswerLatch(ctx_api, obj["event_id"], from_id, peer_id)

        # шаг 2-3: пред-валидация payload
        try:
            parsed = decode_payload(raw_payload, self.config.secret)
        except InvalidPayload:
            await self._refuse(latch)
            return
        if kind == "message_event" and parsed is None:
            return  # чужое событие (не наш __vkd__) — без ack

        message_manager = MessageManager(ctx_api, media_resolver=self.config.media_resolver)
        async with self.locks.acquire(ev.stack_key):
            # M3: любое неожиданное исключение в теле под lock'ом (не только
            # в _dispatch) обязано ack'нуть message_event перед пробросом —
            # иначе VK-клиент виснет со спиннером навечно. latch.answer()
            # идемпотентен (answered-флаг), так что двойной ack ниже по коду
            # безопасен.
            try:
                stack = await self.proxy.load_stack(ev.stack_key)
                if kind == "message_new":
                    inline = client_info.get("inline_keyboard")
                    if inline is not None:
                        stack.inline_supported = inline
                if parsed is None and stack.empty():
                    return  # обычное сообщение вне диалога — путь пользовательских хендлеров
                try:
                    context = await self._validate(parsed, stack)
                except (UnknownIntent, UnknownState, OutdatedIntent, InvalidPayload) as e:
                    # Гейтим и путь восстановления: иначе не-админ, кликающий
                    # чужое/устаревшее меню в беседе (типичный случай — общее
                    # меню на всех), получал бы НОВОЕ меню в обход валидатора.
                    # context ещё не загружен → проверка по stack.access_settings
                    # (DefaultAccessValidator это поддерживает, context=None).
                    if not await self._is_access_allowed(stack, None, ev):
                        await self._deny_access(latch)
                        return
                    await self._recover(e, ev, stack, message_manager, ctx_api, latch)
                    return
                if context is None:  # message_new без payload при активном диалоге
                    if not await self._is_access_allowed(stack, None, ev):
                        await self._deny_access(latch)
                        return
                    context = await self._load_top_or_recover(
                        ev, stack, message_manager, ctx_api, latch
                    )
                    if context is None:
                        return

                if not await self._is_access_allowed(stack, context, ev):
                    # Валидатор (спека §4.2) — ПОСЛЕ структурного owner-check
                    # (тот отсеивается раньше, через несовпадение
                    # context.stack_key/stack.key в _validate). Тихий ack без
                    # текста; снекбар — опциональный, решение пользователя.
                    await self._deny_access(latch)
                    return

                manager = ManagerImpl(
                    event_ctx=ev,
                    registry=self.registry,
                    proxy=self.proxy,
                    message_manager=message_manager,
                    locks=self.locks,
                    config=self.config,
                    stack=stack,
                    context=context,
                    event=obj,
                    middleware_data={"ctx_api": ctx_api},
                )
                manager._answer_latch = latch
                try:
                    processed = await self._dispatch(manager, parsed, kind, obj)
                except CancelEventProcessing:
                    processed = None  # подавить перерисовку
                except Exception:
                    if latch is not None:
                        await latch.answer()
                    await manager.commit()
                    raise  # -> vkbottle error_handler
                if latch is not None and not latch.answered:
                    await latch.answer()  # ack до рендера (latency budget, спека §5)
                if processed is not None and self._need_refresh(manager, context, processed):
                    await manager.show()
                await manager.commit()
            except Exception:
                if latch is not None and not latch.answered:
                    await latch.answer()
                raise

    async def _is_access_allowed(self, stack: Any, context: Any, ev: EventContext) -> bool:
        validator = self.config.access_validator
        if validator is None:
            return True
        return await validator.is_allowed(stack, context, ev)

    async def _deny_access(self, latch: AnswerLatch | None) -> None:
        # Тихий отказ (спека §4.2): ack без event_data, снекбар опционален.
        if latch is not None:
            await latch.answer(snackbar=self.config.access_denied_snackbar)

    async def _validate(self, parsed: ParsedPayload | None, stack: Any) -> Any:
        if parsed is None:
            return None
        if stack.last_intent_id() != parsed.intent_id:
            raise OutdatedIntent(stack.key, "intent не вершина стека события")
        context = await self.proxy.load_context(parsed.intent_id)
        if context.stack_key != stack.key:
            raise InvalidPayload("context.stack_key != стек события")
        return context

    async def _load_top_or_recover(
        self,
        ev: EventContext,
        stack: Any,
        mm: MessageManager,
        ctx_api: Any,
        latch: AnswerLatch | None,
    ) -> Any:
        try:
            return await self.proxy.load_top(stack)
        except (UnknownIntent, UnknownState) as e:
            await self._recover(e, ev, stack, mm, ctx_api, latch)
            return None

    async def _dispatch(
        self, manager: ManagerImpl, parsed: ParsedPayload | None, kind: str, obj: dict
    ) -> bool:
        dialog = manager.dialog()
        if parsed is not None:
            return await dialog.process_callback(parsed.callback_data, manager)
        msg = obj["message"]
        message = SimpleNamespace(
            text=msg.get("text", ""),
            attachments=[
                SimpleNamespace(**a) if isinstance(a, dict) else a
                for a in msg.get("attachments", [])
            ],
            raw=msg,
        )
        return await dialog.process_message(message, manager)

    def _need_refresh(self, manager: ManagerImpl, original_ctx: Any, processed: bool) -> bool:
        # порт Dialog._need_refresh (спека §5, шаг 8)
        if not manager.has_context():
            return False
        if not original_ctx.same(manager.current_context()):
            return False  # навигация уже отрендерила
        if processed:
            return True
        return not manager._event_ctx.is_chat  # приватный чат — рендерим всегда

    async def _refuse(self, latch: AnswerLatch | None) -> None:
        if latch is not None:
            await latch.answer(snackbar=self.config.stale_snackbar)

    async def _recover(
        self,
        error: DialogError,
        ev: EventContext,
        stack: Any,
        message_manager: MessageManager,
        ctx_api: Any,
        latch: AnswerLatch | None,
    ) -> None:
        logger.debug("dialog recover: %r", error)
        await self.proxy.repair(stack)
        handler = (
            self.on_unknown_state if isinstance(error, UnknownState) else self.on_unknown_intent
        )
        if handler is not None:
            manager = ManagerImpl(
                event_ctx=ev,
                registry=self.registry,
                proxy=self.proxy,
                message_manager=message_manager,
                locks=self.locks,
                config=self.config,
                stack=stack,
                context=None,
                event=ev.raw,
            )
            manager._answer_latch = latch
            await handler(ev.raw, manager)
            await manager.commit()
        await self._refuse(latch)


__all__ = ["AnswerLatch", "DialogView"]
