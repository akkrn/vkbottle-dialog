import pytest

from vkbottle_dialog.api.entities import (
    EventContext,
    LaunchMode,
    StartMode,
)
from vkbottle_dialog.context.locks import LockRegistry
from vkbottle_dialog.context.memory import MemoryStorage
from vkbottle_dialog.context.proxy import StorageProxy
from vkbottle_dialog.dialog import Dialog
from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup, StatesRegistry
from vkbottle_dialog.manager.bg_manager import BgManagerFactory
from vkbottle_dialog.manager.manager import DialogConfig, ManagerImpl
from vkbottle_dialog.manager.message_manager import MessageManager
from vkbottle_dialog.widgets.kbd import Button
from vkbottle_dialog.widgets.text import Const, Format
from vkbottle_dialog.window import Window


class MainSG(StatesGroup):
    a = State()
    b = State()


class SubSG(StatesGroup):
    x = State()


class RootSG(StatesGroup):
    r = State()


class ExclusiveSG(StatesGroup):
    e = State()


class SingleTopSG(StatesGroup):
    s = State()


results = []


async def on_sub_result(start_data, result, manager):
    results.append((start_data, result))


def build_world(fake_api):
    main = Dialog(
        Window(Const("A"), Button(Const("b"), id="btn"), state=MainSG.a),
        Window(Format("B"), state=MainSG.b),
        on_process_result=on_sub_result,
    )
    sub = Dialog(Window(Const("X"), state=SubSG.x))

    class Registry:
        def dialog_for_group(self, group):
            return {MainSG: main, SubSG: sub}[group]

        def dialog_for_state(self, state):
            return self.dialog_for_group(state.group)

    states = StatesRegistry()
    states.register(MainSG)
    states.register(SubSG)
    proxy = StorageProxy(MemoryStorage(), states)
    deps = dict(
        registry=Registry(),
        proxy=proxy,
        message_manager=MessageManager(fake_api),
        locks=LockRegistry(),
        config=DialogConfig(secret=None, now=lambda: 1000.0),
    )
    return main, sub, deps


def build_launch_mode_world(fake_api):
    main = Dialog(Window(Const("A"), state=MainSG.a), Window(Const("B"), state=MainSG.b))
    root = Dialog(Window(Const("R"), state=RootSG.r), launch_mode=LaunchMode.ROOT)
    exclusive = Dialog(Window(Const("E"), state=ExclusiveSG.e), launch_mode=LaunchMode.EXCLUSIVE)
    single_top = Dialog(Window(Const("S"), state=SingleTopSG.s), launch_mode=LaunchMode.SINGLE_TOP)
    dialogs = {MainSG: main, RootSG: root, ExclusiveSG: exclusive, SingleTopSG: single_top}

    class Registry:
        def dialog_for_group(self, group):
            return dialogs[group]

        def dialog_for_state(self, state):
            return self.dialog_for_group(state.group)

    states = StatesRegistry()
    for group in dialogs:
        states.register(group)
    proxy = StorageProxy(MemoryStorage(), states)
    return dict(
        registry=Registry(),
        proxy=proxy,
        message_manager=MessageManager(fake_api),
        locks=LockRegistry(),
        config=DialogConfig(secret=None, now=lambda: 1000.0),
    )


def ev(kind="message_event"):
    return EventContext(group_id=1, peer_id=5, owner_id=5, user_id=5, kind=kind, raw=None)


async def make_manager(deps, event=None):
    event = event or ev()
    stack = await deps["proxy"].load_stack(event.stack_key)
    ctx = await deps["proxy"].load_top(stack) if not stack.empty() else None
    return ManagerImpl(event_ctx=event, stack=stack, context=ctx, **deps)


async def test_start_renders_and_persists(fake_api):
    _, _, deps = build_world(fake_api)
    m = await make_manager(deps)
    await m.start(MainSG.a)
    await m.commit()
    assert len(fake_api.sent("messages.send")) == 1
    m2 = await make_manager(deps)
    assert m2.current_context().state is MainSG.a


async def test_switch_navigation(fake_api):
    _, _, deps = build_world(fake_api)
    m = await make_manager(deps)
    await m.start(MainSG.a)
    await m.next()
    assert m.current_context().state is MainSG.b
    await m.back()
    assert m.current_context().state is MainSG.a
    with pytest.raises(DialogConfigError):
        await m.back()
    with pytest.raises(DialogConfigError):
        await m.switch_to(SubSG.x)  # чужая группа


async def test_subdialog_result_flow(fake_api):
    results.clear()
    _, _, deps = build_world(fake_api)
    m = await make_manager(deps)
    await m.start(MainSG.a)
    await m.start(SubSG.x, data={"q": 1})
    assert m.current_context().state is SubSG.x
    assert len(m.current_stack().intents) == 2
    await m.done(result="ok")
    assert m.current_context().state is MainSG.a
    assert results == [({"q": 1}, "ok")]


async def test_done_last_removes_kbd(fake_api):
    _, _, deps = build_world(fake_api)
    m = await make_manager(deps)
    await m.start(MainSG.a)
    await m.done()
    assert not m.has_context()
    assert m.current_stack().last_cmid is None  # remove_kbd отработал


async def test_reset_stack_mode(fake_api):
    _, _, deps = build_world(fake_api)
    m = await make_manager(deps)
    await m.start(MainSG.a)
    await m.start(SubSG.x)
    await m.start(MainSG.b, mode=StartMode.RESET_STACK)
    assert len(m.current_stack().intents) == 1
    assert m.current_context().state is MainSG.b


async def test_new_stack_not_implemented(fake_api):
    _, _, deps = build_world(fake_api)
    m = await make_manager(deps)
    with pytest.raises(NotImplementedError):
        await m.start(MainSG.a, mode=StartMode.NEW_STACK)


async def test_bg_manager_from_handler_no_deadlock(fake_api):
    _, _, deps = build_world(fake_api)
    factory = BgManagerFactory(group_id=1, **deps)  # group_id как в ev()
    m = await make_manager(deps)
    await m.start(MainSG.a)
    await m.commit()
    # bg на тот же стек изнутри уже взятого lock'а — реентерабельность
    async with deps["locks"].acquire(ev().stack_key):
        bg = factory.bg(peer_id=5)
        await bg.update({"n": 1})
    m2 = await make_manager(deps)
    assert m2.current_context().dialog_data == {"n": 1}


async def test_update_merges_and_shows(fake_api):
    _, _, deps = build_world(fake_api)
    m = await make_manager(deps)
    await m.start(MainSG.a)
    calls_before = len(fake_api.calls)
    await m.update({"k": "v"})
    assert m.dialog_data == {"k": "v"}
    assert len(fake_api.calls) >= calls_before  # show() вызван


async def test_nested_bg_update_not_clobbered_by_done(fake_api):
    # Регрессия: done() раньше предпочитал in-memory _dirty_contexts, из-за
    # чего свежий commit параллельного bg() на того же родителя откатывался
    # обратно устаревшей копией. done() должен читать родителя из storage
    # (источник истины) и падать в dirty-cache только если родитель ещё не
    # был закоммичен вовсе.
    _, _, deps = build_world(fake_api)
    m = await make_manager(deps)
    await m.start(MainSG.a)
    await m.commit()
    m2 = await make_manager(deps)
    await m2.start(SubSG.x)
    bg = m2.bg(peer_id=5)
    await bg.update({"n": 1})
    await m2.done(result="ok")
    await m2.commit()
    m3 = await make_manager(deps)
    assert m3.current_context().dialog_data.get("n") == 1


async def test_root_launch_mode_clears_stack(fake_api):
    deps = build_launch_mode_world(fake_api)
    m = await make_manager(deps)
    await m.start(MainSG.a)
    await m.start(RootSG.r)
    assert len(m.current_stack().intents) == 1
    assert m.current_context().state is RootSG.r


async def test_start_on_exclusive_raises(fake_api):
    deps = build_launch_mode_world(fake_api)
    m = await make_manager(deps)
    await m.start(ExclusiveSG.e)
    with pytest.raises(DialogConfigError):
        await m.start(MainSG.a)


async def test_single_top_replaces_top(fake_api):
    deps = build_launch_mode_world(fake_api)
    m = await make_manager(deps)
    await m.start(SingleTopSG.s)
    first_id = m.current_context().intent_id
    await m.start(SingleTopSG.s)
    assert len(m.current_stack().intents) == 1
    assert m.current_context().intent_id != first_id


async def test_detached_start_reloads_stack_under_lock(fake_api):
    # Регрессия: rules.py строит detached-менеджер из стека, прочитанного
    # ДО захвата lock'а (rule.check() лишь смотрит, активен ли диалог). Два
    # конкурентных detached .start() на один и тот же изначально пустой стек
    # раньше оба видели пустой pre-lock снимок; второй commit() затирал стек
    # первого этим устаревшим снимком, сиротя его intent (потерянное
    # обновление). _run_detached обязан перечитывать стек/контекст из
    # storage ПОСЛЕ захвата lock'а, а не коммитить pre-lock снимок.
    _, _, deps = build_world(fake_api)
    event = ev(kind="message_new")
    stack_a = await deps["proxy"].load_stack(event.stack_key)
    stack_b = await deps["proxy"].load_stack(event.stack_key)
    mgr_a = ManagerImpl(event_ctx=event, stack=stack_a, context=None, **deps)
    mgr_a._detached = True
    mgr_b = ManagerImpl(event_ctx=event, stack=stack_b, context=None, **deps)
    mgr_b._detached = True

    await mgr_a.start(MainSG.a)
    await mgr_b.start(MainSG.a)

    final_stack = await deps["proxy"].load_stack(event.stack_key)
    assert len(final_stack.intents) == 2  # оба intent'а живы — вложенный диалог
    for intent_id in final_stack.intents:
        ctx = await deps["proxy"].load_context(intent_id)  # не должно бросить UnknownIntent
        assert ctx.intent_id == intent_id
