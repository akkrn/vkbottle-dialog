from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..context.locks import LockRegistry
from ..context.memory import MemoryStorage
from ..context.proxy import StorageProxy
from ..dialog import Dialog
from ..exceptions import DialogConfigError
from ..fsm import State, StatesRegistry
from ..manager.bg_manager import BgManagerFactory
from ..manager.manager import DialogConfig
from ..manager.message_manager import MessageManager
from .view import DialogView

_ACTIVE: SetupDeps | None = None


class DialogRegistry:
    def __init__(self, *dialogs: Dialog, states_registry: StatesRegistry) -> None:
        self._by_group: dict = {}
        for dialog in dialogs:
            group = dialog.states_group()
            if group in self._by_group:
                raise DialogConfigError(f"два Dialog на одну группу {group.__name__}")
            self._by_group[group] = dialog
            states_registry.register(group)

    def dialog_for_group(self, group: type) -> Dialog:
        try:
            return self._by_group[group]
        except KeyError:
            raise DialogConfigError(f"нет диалога для {group.__name__}") from None

    def dialog_for_state(self, state: State) -> Dialog:
        return self.dialog_for_group(state.group)


class SetupDeps:
    def __init__(
        self,
        registry: DialogRegistry,
        proxy: StorageProxy,
        locks: LockRegistry,
        config: DialogConfig,
        bg_factory: BgManagerFactory,
        api: Any,
    ) -> None:
        self.registry = registry
        self.proxy = proxy
        self.locks = locks
        self.config = config
        self.bg_factory = bg_factory
        self._api = api

    def message_manager(self, ctx_api: Any = None) -> MessageManager:
        return MessageManager(ctx_api or self._api)

    def group_id(self) -> int:
        return self.bg_factory._group_id


def active_setup() -> SetupDeps:
    if _ACTIVE is None:
        raise DialogConfigError("setup_dialogs не вызван")
    return _ACTIVE


def setup_dialogs(
    bot: Any,
    *dialogs: Dialog,
    storage: Any = None,
    payload_secret: str | None = None,
    getter: Any = None,
    markup_factory: Any = None,
    api: Any = None,
    on_unknown_intent: Callable | None = None,
    on_unknown_state: Callable | None = None,
    stale_snackbar: str = "Окно устарело, начните заново",
) -> BgManagerFactory:
    """Подключает диалоги к боту и возвращает BgManagerFactory для bg()
    из внешнего кода (крон, вебхуки и т.п.).

    ВАЖНО: vkbottle не блокирует события между views — DialogView лишь один
    из views в labeler.views(), выполняется наравне с остальными. Хендлеры,
    зарегистрированные БЕЗ InDialog()/NotInDialog(), сработают поверх
    активного диалога как обычно (диалог их не "перехватывает" и не
    блокирует). Используйте InDialog()/NotInDialog(), чтобы хендлер
    учитывал состояние диалога (см. README, задача 19, для деталей и
    примеров сосуществования с обычными хендлерами)."""
    global _ACTIVE
    states_registry = StatesRegistry()
    registry = DialogRegistry(*dialogs, states_registry=states_registry)
    proxy = StorageProxy(storage or MemoryStorage(), states_registry)
    locks = LockRegistry()
    config = DialogConfig(
        secret=payload_secret, global_getter=getter, stale_snackbar=stale_snackbar
    )
    if markup_factory is not None:
        config.default_markup_factory = markup_factory
    the_api = api or bot.api
    bg_factory = BgManagerFactory(
        registry=registry,
        proxy=proxy,
        message_manager=MessageManager(the_api),
        locks=locks,
        config=config,
    )
    view = DialogView(
        registry=registry,
        proxy=proxy,
        locks=locks,
        config=config,
        bg_factory=bg_factory,
        on_unknown_intent=on_unknown_intent,
        on_unknown_state=on_unknown_state,
    )
    # КРИТИЧНО: bot.router.add_view не работает (Bot.router — property,
    # пересобирающая views из labeler на каждом событии) — оборачиваем labeler.
    # DialogView ставится ПЕРВЫМ: на message_new без активного диалога (ещё
    # не стартован) он обязан молча пропустить событие ДО того, как
    # пользовательский message-хендлер (например NotInDialog + /start)
    # создаст диалог — иначе тот же message_new будет продиспатчен в уже
    # созданный (в рамках этого же route()) диалог как текстовый ввод и
    # вызовет повторную отправку окна.
    original_views = bot.labeler.views
    bot.labeler.views = lambda: {"vkd_dialog": view, **original_views()}
    _ACTIVE = SetupDeps(registry, proxy, locks, config, bg_factory, the_api)
    return bg_factory


__all__ = ["DialogRegistry", "SetupDeps", "active_setup", "setup_dialogs"]
