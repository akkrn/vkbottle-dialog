import json

import pytest
from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.api.entities import (
    AccessSettings,
    Context,
    EventContext,
    Stack,
    make_stack_key,
)
from vkbottle_dialog.context.access_validator import DefaultAccessValidator
from vkbottle_dialog.context.locks import LockRegistry
from vkbottle_dialog.context.memory import MemoryStorage
from vkbottle_dialog.context.proxy import StorageProxy
from vkbottle_dialog.fsm import State, StatesGroup, StatesRegistry
from vkbottle_dialog.integration.rules import NotInDialog
from vkbottle_dialog.integration.setup import active_setup
from vkbottle_dialog.manager.manager import DialogConfig, ManagerImpl
from vkbottle_dialog.manager.message_manager import MessageManager
from vkbottle_dialog.payload import encode_payload
from vkbottle_dialog.widgets.kbd import Button, Start
from vkbottle_dialog.widgets.text import Const


class SG(StatesGroup):
    menu = State()


def dm_event(user_id=7):
    return EventContext(
        group_id=1,
        peer_id=user_id,
        owner_id=user_id,
        user_id=user_id,
        kind="message_event",
        raw=None,
    )


def chat_event(user_id):
    peer = 2_000_000_001
    return EventContext(
        group_id=1, peer_id=peer, owner_id=user_id, user_id=user_id, kind="message_event", raw=None
    )


def make_stack():
    return Stack(key=make_stack_key(1, 2_000_000_001, 7))


def make_ctx(access_settings=None):
    return Context(
        intent_id="i1",
        stack_key=make_stack_key(1, 2_000_000_001, 7),
        state=SG.menu,
        start_data=None,
        access_settings=access_settings,
    )


# --- DefaultAccessValidator (unit) ---


async def test_dm_always_allowed_regardless_of_settings():
    validator = DefaultAccessValidator()
    stack = make_stack()
    ctx = make_ctx(AccessSettings([999]))
    assert await validator.is_allowed(stack, ctx, dm_event(7)) is True


async def test_chat_allows_listed_user_id():
    validator = DefaultAccessValidator()
    stack = make_stack()
    ctx = make_ctx(AccessSettings([7]))
    assert await validator.is_allowed(stack, ctx, chat_event(7)) is True


async def test_chat_denies_unlisted_user_id():
    validator = DefaultAccessValidator()
    stack = make_stack()
    ctx = make_ctx(AccessSettings([7]))
    assert await validator.is_allowed(stack, ctx, chat_event(8)) is False


async def test_chat_settings_none_on_context_is_open_even_with_stack_restriction():
    # легаси: контекст загружен, его поле None → доступ ОТКРЫТ, даже если у
    # стека есть более узкие settings — контекст выигрывает.
    validator = DefaultAccessValidator()
    stack = Stack(key=make_stack_key(1, 2_000_000_001, 7), access_settings=AccessSettings([999]))
    ctx = make_ctx(access_settings=None)
    assert await validator.is_allowed(stack, ctx, chat_event(8)) is True


async def test_chat_falls_back_to_stack_settings_when_context_not_loaded():
    validator = DefaultAccessValidator()
    stack = Stack(key=make_stack_key(1, 2_000_000_001, 7), access_settings=AccessSettings([7]))
    assert await validator.is_allowed(stack, None, chat_event(7)) is True
    assert await validator.is_allowed(stack, None, chat_event(8)) is False


async def test_chat_empty_user_ids_is_open():
    validator = DefaultAccessValidator()
    stack = make_stack()
    ctx = make_ctx(AccessSettings([]))
    assert await validator.is_allowed(stack, ctx, chat_event(999)) is True


async def test_custom_validator_can_block_regardless_of_settings():
    class AlwaysDeny:
        async def is_allowed(self, stack, context, event_ctx):
            return False

    validator = AlwaysDeny()
    stack = make_stack()
    ctx = make_ctx(None)
    assert await validator.is_allowed(stack, ctx, chat_event(7)) is False


# --- hook в DialogView: тихий отказ, on_click не вызван ---


def raw_message_event(payload: dict, peer, user, cmid=101):
    return {
        "type": "message_event",
        "group_id": 99,
        "object": {
            "event_id": "ev1",
            "user_id": user,
            "peer_id": peer,
            "conversation_message_id": cmid,
            "payload": payload,
        },
    }


@pytest.fixture
def access_world(fake_api):
    clicked = []

    async def on_click(event, widget, manager):
        clicked.append("clicked")

    dialog = Dialog(
        Window(Const("Меню"), Button(Const("Жми"), id="go", on_click=on_click), state=SG.menu),
    )
    bot = Bot("token")
    bg = setup_dialogs(bot, dialog, storage=MemoryStorage(), api=fake_api)
    return bot, fake_api, clicked, bg


async def test_hook_silently_acks_when_validator_denies(access_world):
    # Естественная per-owner маршрутизация в v0.3 не даёт разным from_id
    # попасть в один и тот же стек — валидатор тестируется через явно
    # заданный AccessSettings на контексте владельца, чей клик после этого
    # сам оказывается за пределами списка (например, окно временно закрыто
    # для всех, кроме конкретного согласующего user_id).
    bot, api, clicked, bg = access_world
    chat_peer = 2_000_000_001

    @bot.on.message(NotInDialog(), text="/start")
    async def start(message, dialog_manager):
        await dialog_manager.start(SG.menu, mode=StartMode.RESET_STACK)

    msg = {
        "id": 0,
        "conversation_message_id": 10,
        "peer_id": chat_peer,
        "from_id": 7,
        "text": "/start",
        "attachments": [],
        "date": 0,
        "version": 0,
        "out": 0,
        "fwd_messages": [],
        "client_info": {
            "inline_keyboard": True,
            "button_actions": [],
            "keyboard": True,
            "lang_id": 0,
        },
    }
    event = {
        "type": "message_new",
        "group_id": 99,
        "object": {"message": msg, "client_info": msg["client_info"]},
    }
    await bot.router.route(event, api)

    kb = json.loads(api.sent("messages.send")[-1]["keyboard"])
    payload = json.loads(kb["buttons"][0][0]["action"]["payload"])
    intent = payload["__vkd__"].split("|")[0]

    # Ограничиваем доступ к контексту владельца user_ids=[999] — сам
    # владелец (7) больше не проходит валидатор, хотя структурно это его
    # собственный стек (owner-check пройден).
    deps = active_setup()
    stack = await deps.proxy.load_stack(make_stack_key(99, chat_peer, 7))
    ctx = await deps.proxy.load_top(stack)
    ctx.access_settings = AccessSettings([999])
    await deps.proxy.save(stack, ctx)

    cb_payload = json.loads(encode_payload(intent, "go", None))
    await bot.router.route(raw_message_event(cb_payload, peer=chat_peer, user=7), api)

    assert clicked == []  # on_click НЕ вызван
    answers = api.sent("messages.sendMessageEventAnswer")
    assert len(answers) == 1
    assert "event_data" not in answers[0]  # тихий ack без текста


# --- наследование access_settings в start() ---


class InheritSG(StatesGroup):
    a = State()


def build_deps(fake_api):
    inherit_dialog = Dialog(Window(Const("A"), state=InheritSG.a))

    class Registry:
        def dialog_for_group(self, group):
            return inherit_dialog

        def dialog_for_state(self, state):
            return self.dialog_for_group(state.group)

    states = StatesRegistry()
    states.register(InheritSG)
    proxy = StorageProxy(MemoryStorage(), states)
    return dict(
        registry=Registry(),
        proxy=proxy,
        message_manager=MessageManager(fake_api),
        locks=LockRegistry(),
        config=DialogConfig(secret=None, now=lambda: 1000.0),
    )


async def make_mgr(deps, event_ctx):
    stack = await deps["proxy"].load_stack(event_ctx.stack_key)
    ctx = await deps["proxy"].load_top(stack) if not stack.empty() else None
    return ManagerImpl(event_ctx=event_ctx, stack=stack, context=ctx, **deps)


async def test_start_uses_explicit_access_settings_over_parent_and_stack(fake_api):
    deps = build_deps(fake_api)
    ev = EventContext(
        group_id=1, peer_id=2_000_000_001, owner_id=7, user_id=7, kind="message_event", raw=None
    )
    m = await make_mgr(deps, ev)
    explicit = AccessSettings([111])
    await m.start(InheritSG.a, access_settings=explicit)
    assert m.current_context().access_settings == AccessSettings([111])
    # deepcopy: мутация исходного объекта не протекает в контекст
    explicit.user_ids.append(222)
    assert m.current_context().access_settings == AccessSettings([111])


async def test_start_inherits_parent_context_access_settings(fake_api):
    deps = build_deps(fake_api)
    ev = EventContext(
        group_id=1, peer_id=2_000_000_001, owner_id=7, user_id=7, kind="message_event", raw=None
    )
    m = await make_mgr(deps, ev)
    await m.start(InheritSG.a, access_settings=AccessSettings([7]))
    parent_settings = m.current_context().access_settings
    await m.start(InheritSG.a)  # без явного access_settings -> наследует родителя
    assert m.current_context().access_settings == AccessSettings([7])
    assert m.current_context().access_settings is not parent_settings  # deepcopy, не тот же объект


async def test_start_falls_back_to_stack_access_settings_with_no_parent(fake_api):
    deps = build_deps(fake_api)
    ev = EventContext(
        group_id=1, peer_id=2_000_000_001, owner_id=7, user_id=7, kind="message_event", raw=None
    )
    m = await make_mgr(deps, ev)
    assert not m.has_context()
    stack_settings = m.current_stack().access_settings
    assert stack_settings == AccessSettings([7])  # per-owner дефолт из parse_stack_key
    await m.start(InheritSG.a)
    assert m.current_context().access_settings == AccessSettings([7])
    assert m.current_context().access_settings is not stack_settings


async def test_start_button_widget_passes_access_settings_through(fake_manager_factory):
    m = fake_manager_factory(SG.menu)
    settings = AccessSettings([42])
    btn = Start(Const("go"), id="go", state=InheritSG.a, access_settings=settings)
    await btn.process_callback("go", m)
    assert m.calls == [("start", InheritSG.a, None, settings)]
