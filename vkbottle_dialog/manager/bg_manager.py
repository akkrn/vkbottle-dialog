from __future__ import annotations

from typing import Any

from ..api.entities import EventContext, ShowMode, StartMode
from ..context.locks import LockRegistry
from ..context.proxy import StorageProxy
from ..fsm import State
from .manager import DialogConfig, ManagerImpl
from .message_manager import MessageManager


class BgManager:
    def __init__(self, *, coords: EventContext, registry: Any, proxy: StorageProxy,
                 message_manager: MessageManager, locks: LockRegistry,
                 config: DialogConfig) -> None:
        self._coords = coords
        self._deps = dict(registry=registry, proxy=proxy,
                          message_manager=message_manager, locks=locks, config=config)
        self._locks = locks
        self._proxy = proxy

    async def _run(self, op: Any) -> None:
        async with self._locks.acquire(self._coords.stack_key):
            stack = await self._proxy.load_stack(self._coords.stack_key)
            context = await self._proxy.load_top(stack) if not stack.empty() else None
            manager = ManagerImpl(event_ctx=self._coords, stack=stack,
                                  context=context, **self._deps)
            await op(manager)
            await manager.commit()

    async def start(self, state: State, data: Any = None,
                    mode: StartMode = StartMode.NORMAL,
                    show_mode: ShowMode | None = None) -> None:
        await self._run(lambda m: m.start(state, data, mode, show_mode))

    async def switch_to(self, state: State,
                        show_mode: ShowMode | None = None) -> None:
        async def op(m: ManagerImpl) -> None:
            await m.switch_to(state, show_mode)
            await m.show()
        await self._run(op)

    async def update(self, data: dict, show_mode: ShowMode | None = None) -> None:
        await self._run(lambda m: m.update(data, show_mode))

    async def done(self, result: Any = None,
                   show_mode: ShowMode | None = None) -> None:
        await self._run(lambda m: m.done(result, show_mode))


class BgManagerFactory:
    def __init__(self, *, registry: Any, proxy: StorageProxy,
                 message_manager: MessageManager, locks: LockRegistry,
                 config: DialogConfig, group_id: int = 0) -> None:
        self._deps = dict(registry=registry, proxy=proxy,
                          message_manager=message_manager, locks=locks, config=config)
        self._group_id = group_id

    def set_group_id(self, group_id: int) -> None:
        self._group_id = group_id

    def bg(self, peer_id: int, user_id: int | None = None) -> BgManager:
        owner = user_id if user_id is not None else peer_id
        coords = EventContext(group_id=self._group_id, peer_id=peer_id,
                              owner_id=owner, user_id=owner, kind="bg", raw=None)
        return BgManager(coords=coords, **self._deps)
