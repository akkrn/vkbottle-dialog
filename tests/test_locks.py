import asyncio

from vkbottle_dialog.context.locks import LockRegistry


async def test_mutual_exclusion():
    reg = LockRegistry()
    order: list[str] = []

    async def worker(tag: str):
        async with reg.acquire("k"):
            order.append(f"{tag}-in")
            await asyncio.sleep(0.01)
            order.append(f"{tag}-out")

    await asyncio.gather(worker("a"), worker("b"))
    assert order in (["a-in", "a-out", "b-in", "b-out"], ["b-in", "b-out", "a-in", "a-out"])


async def test_reentrant_same_task():
    reg = LockRegistry()
    async with reg.acquire("k"), reg.acquire("k"):  # не должно зависнуть
        pass


async def test_different_keys_parallel():
    reg = LockRegistry()
    entered = asyncio.Event()

    async def holder():
        async with reg.acquire("a"):
            entered.set()
            await asyncio.sleep(0.05)

    task = asyncio.create_task(holder())
    await entered.wait()
    async with reg.acquire("b"):  # другой ключ — без ожидания
        pass
    await task


async def test_registry_cleanup():
    reg = LockRegistry()
    async with reg.acquire("k"):
        pass
    assert len(reg._locks) == 0


async def test_suspend_releases_lock_for_other_waiters():
    reg = LockRegistry()
    order: list[str] = []

    async def other():
        async with reg.acquire("k"):
            order.append("other-in")

    async with reg.acquire("k"):
        order.append("holder-in")
        task = asyncio.create_task(other())
        async with reg.suspend("k"):
            # lock отпущен — конкурент должен успеть зайти и выйти
            await asyncio.wait_for(task, timeout=1)
        order.append("holder-resumed")
    assert order == ["holder-in", "other-in", "holder-resumed"]


async def test_suspend_reacquires_lock_after_block():
    reg = LockRegistry()
    async with reg.acquire("k"):
        assert reg.held("k")
        async with reg.suspend("k"):
            assert not reg.held("k")
        assert reg.held("k")


async def test_held_false_when_not_acquired():
    reg = LockRegistry()
    assert not reg.held("k")


async def test_spawned_task_does_not_inherit_lock():
    reg = LockRegistry()
    order: list[str] = []

    async def child():
        async with reg.acquire("k"):
            order.append("child-in")

    async with reg.acquire("k"):
        task = asyncio.create_task(child())
        await asyncio.sleep(0.01)
        order.append("parent-out")
    await task
    assert order == ["parent-out", "child-in"]  # ребёнок ждал освобождения
