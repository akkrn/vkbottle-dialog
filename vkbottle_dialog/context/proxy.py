from __future__ import annotations

from typing import Any

from ..api.entities import Context, KeyboardKind, Stack, context_key
from ..api.protocols import BaseStorage
from ..exceptions import UnknownIntent
from ..fsm import StatesRegistry


class StorageProxy:
    def __init__(self, storage: BaseStorage, registry: StatesRegistry) -> None:
        self._storage = storage
        self._registry = registry

    async def load_stack(self, stack_key: str) -> Stack:
        raw = await self._storage.get(stack_key)
        if raw is None:
            return Stack(key=stack_key)
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
    }


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
    }
