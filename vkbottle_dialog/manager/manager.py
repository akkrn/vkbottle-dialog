from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..api.entities import (
    Context,
    EventContext,
    LaunchMode,
    ShowMode,
    Stack,
    StartMode,
)
from ..context.locks import LockRegistry
from ..context.proxy import StorageProxy
from ..exceptions import DialogConfigError, UnknownIntent
from ..fsm import State
from ..widgets.common import ensure_data_getter
from ..widgets.markup import InlineKeyboardFactory, TextKeyboardFactory
from .message_manager import MessageManager


@dataclass
class DialogConfig:
    secret: str | None = None
    default_markup_factory: Any = field(default_factory=InlineKeyboardFactory)
    now: Callable[[], float] = time.time
    global_getter: Any = None
    stale_snackbar: str = "Окно устарело, начните заново"
    media_resolver: Any = None


class ManagerImpl:
    def __init__(
        self,
        *,
        event_ctx: EventContext,
        registry: Any,
        proxy: StorageProxy,
        message_manager: MessageManager,
        locks: LockRegistry,
        config: DialogConfig,
        stack: Stack,
        context: Context | None,
        event: Any = None,
        middleware_data: dict | None = None,
    ) -> None:
        self._event_ctx = event_ctx
        self._registry = registry
        self._proxy = proxy
        self._message_manager = message_manager
        self._locks = locks
        self._config = config
        self._stack = stack
        self._context = context
        self.event = event
        self.middleware_data = middleware_data or {}
        self.show_mode: ShowMode = ShowMode.AUTO
        self._answer_latch: Any = None  # ставит DialogView
        self._detached = False  # ставит правило InDialog/NotInDialog
        self._dirty_contexts: dict[str, Context] = {}
        if context is not None:
            self._dirty_contexts[context.intent_id] = context

    # --- доступ к состоянию ---

    def has_context(self) -> bool:
        return self._context is not None

    def current_context(self) -> Context:
        if self._context is None:
            raise UnknownIntent("нет активного диалога")
        return self._context

    def current_stack(self) -> Stack:
        return self._stack

    @property
    def dialog_data(self) -> dict:
        return self.current_context().dialog_data

    @property
    def start_data(self) -> Any:
        return self.current_context().start_data

    def dialog(self) -> Any:
        return self._registry.dialog_for_group(self.current_context().state.group)

    async def load_data(self) -> dict:
        """Единственная точка сборки данных геттеров: базовые ключи → global
        → dialog-level → window-level (текущего окна). Вызывается и при
        рендере (Window.render → Window.load_data), и на callback-время
        виджетами (ScrollingGroup/BasePager/StubScroll/Toggle) — так данные
        на клике совпадают с данными последнего рендера."""
        data: dict = {
            "dialog_data": self.dialog_data if self.has_context() else {},
            "start_data": self.start_data if self.has_context() else None,
            "middleware_data": self.middleware_data,
            "event": self.event,
            "dialog_manager": self,
        }
        if self._config.global_getter is not None:
            getter = ensure_data_getter(self._config.global_getter)
            data.update(await getter(dialog_manager=self))
        if self.has_context():
            data.update(await self.dialog().load_getter_data(self))
        return data

    def find(self, widget_id: str) -> Any:
        widget = self.dialog().find(widget_id)
        return widget.managed(self) if widget is not None else None

    def find_scroll(self, widget_id: str) -> Any:
        return self.dialog().find_scroll(widget_id)

    # --- навигация ---

    async def _run_detached(self, impl: Callable[..., Any], *args: Any) -> None:
        """Detached-менеджер (из InDialog/NotInDialog) не сидит под чужим
        lock'ом — start/done/update сами берут lock стека и коммитят
        (LockRegistry реентерабелен — вложенный acquire того же стека не
        дедлочится).

        Стек/контекст, с которыми менеджер был сконструирован, читались ДО
        захвата lock'а (rule.check() всего лишь смотрит, активен ли диалог) —
        это снимок может быть устаревшим к моменту, когда мы реально
        захватываем lock (конкурентное событие того же владельца могло
        успеть закоммитить свою версию раньше). Поэтому перечитываем
        стек/контекст из storage ПОСЛЕ захвата lock'а и только тогда
        выполняем impl — иначе commit() перезаписал бы актуальный стек
        устаревшим снимком (потерянное обновление, спека §7)."""
        if not self._detached:
            await impl(*args)
            return
        async with self._locks.acquire(self._event_ctx.stack_key):
            self._detached = False
            try:
                self._stack = await self._proxy.load_stack(self._event_ctx.stack_key)
                self._context = (
                    await self._proxy.load_top(self._stack) if not self._stack.empty() else None
                )
                self._dirty_contexts = {}
                if self._context is not None:
                    self._dirty_contexts[self._context.intent_id] = self._context
                await impl(*args)
                await self.commit()
            finally:
                self._detached = True

    async def start(
        self,
        state: State,
        data: Any = None,
        mode: StartMode = StartMode.NORMAL,
        show_mode: ShowMode | None = None,
    ) -> None:
        await self._run_detached(self._start_impl, state, data, mode, show_mode)

    async def _start_impl(
        self, state: State, data: Any, mode: StartMode, show_mode: ShowMode | None
    ) -> None:
        if show_mode is not None:
            self.show_mode = show_mode
        if mode == StartMode.NEW_STACK:
            raise NotImplementedError("StartMode.NEW_STACK не поддержан в v0.1")
        if mode == StartMode.RESET_STACK:
            await self._clear_stack()
        await self._start_normal(state, data)

    async def _clear_stack(self) -> None:
        for intent_id in self._stack.intents:
            await self._proxy.remove_context(intent_id)
            self._dirty_contexts.pop(intent_id, None)
        self._stack.intents.clear()
        self._context = None

    async def _start_normal(self, state: State, data: Any) -> None:
        new_dialog = self._registry.dialog_for_state(state)
        if self._context is not None:
            current_dialog = self.dialog()
            if current_dialog.launch_mode == LaunchMode.EXCLUSIVE:
                raise DialogConfigError("нельзя стартовать поверх EXCLUSIVE диалога")
            if new_dialog.launch_mode in (LaunchMode.ROOT, LaunchMode.EXCLUSIVE):
                await self._clear_stack()
            elif new_dialog.launch_mode == LaunchMode.SINGLE_TOP and new_dialog is current_dialog:
                await self._pop_current()
        ctx = self._stack.push(state, data)
        self._context = ctx
        self._dirty_contexts[ctx.intent_id] = ctx
        await new_dialog.process_start(self, data, state)
        if ctx.same(self._context):
            await self.show()

    async def _pop_current(self) -> None:
        intent_id = self._stack.pop()
        if intent_id:
            await self._proxy.remove_context(intent_id)
            self._dirty_contexts.pop(intent_id, None)
        self._context = None

    async def switch_to(self, state: State, show_mode: ShowMode | None = None) -> None:
        # Снимаем _detached ДО _run_detached (он временно обнуляет флаг на
        # время reload+impl) — так impl знает, рендерить ли самому. Обычный
        # (не-detached) вызов из хендлера окна ничего не рендерит — это
        # делает DialogView.handle_event по _need_refresh() ПОСЛЕ диспатча
        # (intent_id не меняется → двойной рендер иначе). Detached-вызов
        # (InDialog()-хендлер) — сам себе хвост события: без явного show()
        # здесь переключение состояния осталось бы silent no-op для юзера.
        detached = self._detached
        await self._run_detached(self._switch_to_impl, state, show_mode, detached)

    async def _switch_to_impl(
        self, state: State, show_mode: ShowMode | None, render: bool
    ) -> None:
        ctx = self.current_context()
        if state.group is not ctx.state.group:
            raise DialogConfigError(f"switch_to в чужую группу {state.state}; используйте start()")
        if show_mode is not None:
            self.show_mode = show_mode
        ctx.state = state
        if render:
            await self.show()

    async def next(self, show_mode: ShowMode | None = None) -> None:
        # Как и в switch_to: индекс должен считаться внутри _navigate_impl,
        # ПОСЛЕ возможного reload'а контекста в _run_detached, а не здесь —
        # иначе detached-вызов вычислит цель по pre-lock снимку состояния.
        detached = self._detached
        await self._run_detached(self._navigate_impl, 1, show_mode, detached)

    async def back(self, show_mode: ShowMode | None = None) -> None:
        detached = self._detached
        await self._run_detached(self._navigate_impl, -1, show_mode, detached)

    async def _navigate_impl(self, delta: int, show_mode: ShowMode | None, render: bool) -> None:
        states = self.dialog().states()
        idx = states.index(self.current_context().state)
        target = idx + delta
        if target < 0:
            raise DialogConfigError("back() до первого окна")
        if target >= len(states):
            raise DialogConfigError("next() за последним окном")
        await self._switch_to_impl(states[target], show_mode, render)

    async def done(self, result: Any = None, show_mode: ShowMode | None = None) -> None:
        await self._run_detached(self._done_impl, result, show_mode)

    async def _done_impl(self, result: Any, show_mode: ShowMode | None) -> None:
        if show_mode is not None:
            self.show_mode = show_mode
        closing = self.current_context()
        dialog = self.dialog()
        await dialog.process_close(result, self)
        await self._pop_current()
        parent_id = self._stack.last_intent_id()
        if parent_id is None:
            if self.show_mode != ShowMode.NO_UPDATE:
                if self.show_mode == ShowMode.DELETE_AND_SEND:
                    await self._message_manager._delete_old(self._stack, self._event_ctx.peer_id)
                    self._stack.clear_message()
                else:
                    await self._message_manager.remove_kbd(
                        self._stack, self._event_ctx.peer_id, now=self._config.now()
                    )
            return
        # Storage — источник истины: параллельный bg() на тот же стек мог
        # закоммитить более свежую версию родителя, чем то, что лежит в
        # in-memory _dirty_contexts этого менеджера. In-memory версия — только
        # запасной вариант на случай, если родитель ещё не был закоммичен
        # вовсе (иначе тут был бы UnknownIntent).
        parent: Context
        try:
            parent = await self._proxy.load_context(parent_id)
        except UnknownIntent:
            dirty_parent = self._dirty_contexts.get(parent_id)
            if dirty_parent is None:
                raise
            parent = dirty_parent
        self._context = parent
        self._dirty_contexts[parent.intent_id] = parent
        parent_dialog = self.dialog()
        await parent_dialog.process_result(closing.start_data, result, self)
        if parent.same(self._context):
            await parent_dialog.process_window_result(closing.start_data, result, self)
        if parent.same(self._context):
            await self.show()

    async def update(self, data: dict, show_mode: ShowMode | None = None) -> None:
        await self._run_detached(self._update_impl, data, show_mode)

    async def _update_impl(self, data: dict, show_mode: ShowMode | None) -> None:
        self.dialog_data.update(data)
        if show_mode is not None:
            self.show_mode = show_mode
        await self.show()

    async def reset_stack(self, remove_keyboard: bool = True) -> None:
        await self._clear_stack()
        if remove_keyboard:
            await self._message_manager.remove_kbd(
                self._stack, self._event_ctx.peer_id, now=self._config.now()
            )

    # --- рендер и ответы ---

    async def show(self) -> None:
        if self.show_mode == ShowMode.NO_UPDATE:
            self.show_mode = ShowMode.AUTO
            return
        ctx = self.current_context()
        # Деградация для клиентов без inline (спека §6): только в ЛС,
        # по capability из Stack (снята с последнего message_new).
        factory = self._config.default_markup_factory
        if not self._event_ctx.is_chat and self._stack.inline_supported is False:
            factory = TextKeyboardFactory()
        new_message = await self.dialog().render(
            self,
            self._event_ctx,
            ctx.intent_id,
            self._config.secret,
            factory,
        )
        new_message.show_mode = self.show_mode
        await self._message_manager.show_message(
            new_message,
            self._stack,
            trigger=self._event_ctx.kind,
            now=self._config.now(),
        )
        self.show_mode = ShowMode.AUTO

    async def answer(self, snackbar: str | None = None, open_link: str | None = None) -> None:
        if self._answer_latch is not None:
            await self._answer_latch.answer(snackbar=snackbar, open_link=open_link)

    def bg(self, peer_id: int | None = None, user_id: int | None = None) -> Any:
        """Возвращает BgManager для отправки другому peer/пользователю (или
        для использования вне обработки события — крон, вебхуки).

        НЕ ПОДДЕРЖИВАЕТСЯ (v0.1): вызов bg() БЕЗ peer_id/user_id (то есть на
        ТЕКУЩИЙ стек) изнутри хендлера того же события, что уже держит этот
        manager. bg() коммитит под собственным lock'ом сразу, а внешний
        manager закоммитит свою (более раннюю) версию контекста уже после
        возврата из хендлера — итоговый commit() перезапишет изменения
        bg(), потерянное обновление. Внутри хендлера для ТЕКУЩЕГО стека
        используйте методы manager напрямую (update/switch_to/...), bg() —
        для других peer/пользователей."""
        from .bg_manager import BgManager  # цикл: bg_manager импортирует ManagerImpl

        ev = self._event_ctx
        peer = peer_id if peer_id is not None else ev.peer_id
        owner = user_id if user_id is not None else (ev.owner_id if peer == ev.peer_id else peer)
        coords = EventContext(
            group_id=ev.group_id, peer_id=peer, owner_id=owner, user_id=owner, kind="bg", raw=None
        )
        return BgManager(
            coords=coords,
            registry=self._registry,
            proxy=self._proxy,
            message_manager=self._message_manager,
            locks=self._locks,
            config=self._config,
        )

    # --- персист ---

    async def commit(self) -> None:
        alive = {i: c for i, c in self._dirty_contexts.items() if i in self._stack.intents}
        await self._proxy.save(self._stack, *alive.values())
        await self._proxy.touch_all(self._stack)
