import pytest

from vkbottle_dialog.api.entities import make_stack_key
from vkbottle_dialog.context.memory import MemoryStorage
from vkbottle_dialog.context.proxy import StorageProxy
from vkbottle_dialog.exceptions import UnknownIntent
from vkbottle_dialog.fsm import State, StatesGroup, StatesRegistry


class SG(StatesGroup):
    a = State()
    b = State()


@pytest.fixture
def proxy():
    reg = StatesRegistry()
    reg.register(SG)
    return StorageProxy(MemoryStorage(), reg)


KEY = make_stack_key(1, 2, 2)


async def test_missing_stack_is_fresh(proxy):
    stack = await proxy.load_stack(KEY)
    assert stack.key == KEY and stack.empty()


async def test_roundtrip_stack_and_context(proxy):
    stack = await proxy.load_stack(KEY)
    ctx = stack.push(SG.b, {"q": 1})
    ctx.dialog_data["n"] = 7
    stack.last_cmid = 42
    await proxy.save(stack, ctx)

    stack2 = await proxy.load_stack(KEY)
    assert stack2.last_cmid == 42
    top = await proxy.load_top(stack2)
    assert top.same(ctx) and top.state is SG.b
    assert top.dialog_data == {"n": 7} and top.start_data == {"q": 1}


async def test_unknown_intent(proxy):
    with pytest.raises(UnknownIntent):
        await proxy.load_context("nope")


async def test_empty_stack_without_message_deleted(proxy):
    stack = await proxy.load_stack(KEY)
    ctx = stack.push(SG.a, None)
    await proxy.save(stack, ctx)
    stack.pop()
    stack.clear_message()
    await proxy.save(stack)
    assert await proxy._storage.get(KEY) is None


async def test_repair_drops_dead_intents(proxy):
    stack = await proxy.load_stack(KEY)
    c1 = stack.push(SG.a, None)
    stack.push(SG.b, None)  # c2 не сохраняем — «битый» intent
    await proxy.save(stack, c1)
    await proxy.remove_context(stack.intents[-1])

    stack2 = await proxy.load_stack(KEY)
    await proxy.repair(stack2)
    assert stack2.intents == [c1.intent_id]
