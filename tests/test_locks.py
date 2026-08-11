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
    assert order in (["a-in", "a-out", "b-in", "b-out"],
                     ["b-in", "b-out", "a-in", "a-out"])


async def test_reentrant_same_task():
    reg = LockRegistry()
    async with reg.acquire("k"):
        async with reg.acquire("k"):  # не должно зависнуть
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
