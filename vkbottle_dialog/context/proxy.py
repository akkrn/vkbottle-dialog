from __future__ import annotations

from typing import Any

from ..api.entities import (
    AccessSettings,
    Context,
    KeyboardKind,
    Stack,
    context_key,
    parse_stack_key,
)
from ..api.protocols import BaseStorage
from ..exceptions import UnknownIntent
from ..fsm import StatesRegistry


class StorageProxy:
    def __init__(self, storage: BaseStorage, registry: StatesRegistry) -> None:
        self._storage = storage
        self._registry = registry

    async def load_stack(self, stack_key: str) -> Stack:
        _, _, owner_id, _ = parse_stack_key(stack_key)
        try:
            access_settings = AccessSettings([int(owner_id)])
        except ValueError:
            access_settings = AccessSettings([])
        raw = await self._storage.get(stack_key)
        if raw is None:
            return Stack(key=stack_key, access_settings=access_settings)
        return Stack(
            key=stack_key,
            intents=list(raw["intents"]),
            last_cmid=raw["last_cmid"],
            last_message_sent_at=raw["last_message_sent_at"],
            last_keyboard_kind=KeyboardKind(raw["last_keyboard_kind"]),
            last_render_hash=raw["last_render_hash"],
            last_text=raw.get("last_text"),
            inline_supported=raw["inline_supported"],
            last_media_key=raw.get("last_media_key"),
            last_kb_hash=raw.get("last_kb_hash"),
            last_had_carousel=raw.get("last_had_carousel", False),
            access_settings=access_settings,
        )

    async def load_context(self, intent_id: str) -> Context:
        raw = await self._storage.get(context_key(intent_id))
        if raw is None:
            raise UnknownIntent(intent_id)
        return Context(
            intent_id=intent_id,
            stack_key=raw["stack_key"],
            state=self._registry.resolve(raw["state"]),
            start_data=raw["start_data"],
            dialog_data=raw["dialog_data"],
            widget_data=raw["widget_data"],
            access_settings=_load_access_settings(raw.get("access_settings")),
        )

    async def load_top(self, stack: Stack) -> Context | None:
        top = stack.last_intent_id()
        return await self.load_context(top) if top else None

    async def save(self, stack: Stack, *contexts: Context) -> None:
        for ctx in contexts:
            await self._storage.set(context_key(ctx.intent_id), _dump_context(ctx))
        if stack.empty() and stack.last_cmid is None:
            await self._storage.delete(stack.key)
        else:
            await self._storage.set(stack.key, _dump_stack(stack))

    async def remove_context(self, intent_id: str) -> None:
        await self._storage.delete(context_key(intent_id))

    async def repair(self, stack: Stack) -> None:
        alive = []
        for intent_id in stack.intents:
            if await self._storage.get(context_key(intent_id)) is not None:
                alive.append(intent_id)
        stack.intents = alive
        await self.save(stack)

    async def touch_all(self, stack: Stack) -> None:
        await self._storage.touch(stack.key, *(context_key(i) for i in stack.intents))


def _dump_context(ctx: Context) -> dict[str, Any]:
    return {
        "stack_key": ctx.stack_key,
        "state": ctx.state.state,
        "start_data": ctx.start_data,
        "dialog_data": ctx.dialog_data,
        "widget_data": ctx.widget_data,
        "access_settings": _dump_access_settings(ctx.access_settings),
    }


def _dump_access_settings(access_settings: AccessSettings | None) -> dict[str, Any] | None:
    if access_settings is None:
        return None
    return {"user_ids": access_settings.user_ids, "custom": access_settings.custom}


def _load_access_settings(raw: dict[str, Any] | None) -> AccessSettings | None:
    if raw is None:
        return None
    return AccessSettings(user_ids=raw["user_ids"], custom=raw.get("custom"))


def _dump_stack(stack: Stack) -> dict[str, Any]:
    return {
        "intents": stack.intents,
        "last_cmid": stack.last_cmid,
        "last_message_sent_at": stack.last_message_sent_at,
        "last_keyboard_kind": stack.last_keyboard_kind.value,
        "last_render_hash": stack.last_render_hash,
        "last_text": stack.last_text,
        "inline_supported": stack.inline_supported,
        "last_media_key": stack.last_media_key,
        "last_kb_hash": stack.last_kb_hash,
        "last_had_carousel": stack.last_had_carousel,
    }
