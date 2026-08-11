from __future__ import annotations

from typing import Any

from vkbottle.dispatch.rules import ABCRule

from ..api.entities import PEER_ID_OFFSET, EventContext
from ..manager.manager import ManagerImpl
from . import setup as setup_module


def _event_ctx_from_message(message: Any, group_id: int) -> EventContext:
    peer_id = message.peer_id
    from_id = message.from_id
    owner = from_id if peer_id >= PEER_ID_OFFSET else peer_id
    return EventContext(group_id=group_id, peer_id=peer_id, owner_id=owner,
                        user_id=from_id, kind="message_new", raw=message)


async def _detached_manager(message: Any) -> tuple[ManagerImpl, bool]:
    deps = setup_module.active_setup()
    ev = _event_ctx_from_message(message, deps.group_id())
    stack = await deps.proxy.load_stack(ev.stack_key)
    context = None
    if not stack.empty():
        try:
            context = await deps.proxy.load_top(stack)
        except Exception:
            context = None
    manager = ManagerImpl(event_ctx=ev, registry=deps.registry, proxy=deps.proxy,
                          message_manager=deps.message_manager(message.ctx_api),
                          locks=deps.locks, config=deps.config,
                          stack=stack, context=context, event=message)
    manager._detached = True
    return manager, context is not None


class InDialog(ABCRule):
    """Late-binding к единственному setup_dialogs() в процессе (спека §5)."""

    async def check(self, message: Any) -> dict | bool:
        manager, active = await _detached_manager(message)
        return {"dialog_manager": manager} if active else False


class NotInDialog(ABCRule):
    async def check(self, message: Any) -> dict | bool:
        manager, active = await _detached_manager(message)
        return {"dialog_manager": manager} if not active else False


__all__ = ["InDialog", "NotInDialog"]
