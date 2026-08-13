import asyncio

import fakeredis.aioredis

from vkbottle_dialog.context.redis_lock import RedisLockRegistry


async def test_mutual_exclusion_across_instances():
    # два RedisLockRegistry на общем redis-клиенте моделируют два процесса/инстанса
    r = fakeredis.aioredis.FakeRedis()
    reg_a = RedisLockRegistry(r, ttl=5, retry_interval=0.01)
    reg_b = RedisLockRegistry(r, ttl=5, retry_interval=0.01)
    order: list[str] = []

    async def worker(reg, tag):
        async with reg.acquire("k"):
            order.append(f"{tag}-in")
            await asyncio.sleep(0.05)
            order.append(f"{tag}-out")

    await asyncio.gather(worker(reg_a, "a"), worker(reg_b, "b"))
    assert order in (["a-in", "a-out", "b-in", "b-out"], ["b-in", "b-out", "a-in", "a-out"])


async def test_release_does_not_delete_foreign_token():
    r = fakeredis.aioredis.FakeRedis()
    reg = RedisLockRegistry(r, ttl=30, retry_interval=0.01)
    async with reg.acquire("k"):
        # симулируем гонку: TTL истёк, другой инстанс уже перехватил ключ
        await r.set("vkd:lock:k", "someone-else-token")
    # release не должен снять чужой токен
    assert await r.get("vkd:lock:k") == b"someone-else-token"


async def test_heartbeat_keeps_lock_alive_past_ttl():
    r = fakeredis.aioredis.FakeRedis()
    ttl = 0.15
    holder = RedisLockRegistry(r, ttl=ttl, retry_interval=0.02)
    waiter = RedisLockRegistry(r, ttl=ttl, retry_interval=0.02)

    holding = asyncio.Event()
    release = asyncio.Event()

    async def hold():
        async with holder.acquire("k"):
            holding.set()
            await release.wait()

    holder_task = asyncio.create_task(hold())
    await holding.wait()

    waiter_done = asyncio.Event()

    async def wait_for_lock():
        async with waiter.acquire("k"):
            pass
        waiter_done.set()

    waiter_task = asyncio.create_task(wait_for_lock())

    # держим дольше 2 TTL-окон подряд — heartbeat должен продлевать TTL
    await asyncio.sleep(ttl * 2.5)
    assert not waiter_done.is_set()

    release.set()
    await asyncio.wait_for(waiter_done.wait(), timeout=2.0)
    await holder_task
    await waiter_task


async def test_jitter_varies_retry_delays(monkeypatch):
    r = fakeredis.aioredis.FakeRedis()
    # большой ttl — чтобы heartbeat holder'а не успел сработать и не засорил замеры
    holder = RedisLockRegistry(r, ttl=10, retry_interval=0.02, jitter=0.5)
    waiter = RedisLockRegistry(r, ttl=10, retry_interval=0.02, jitter=0.5)

    delays: list[float] = []
    real_sleep = asyncio.sleep

    async def fake_sleep(delay, *args, **kwargs):
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    holding = asyncio.Event()
    release = asyncio.Event()

    async def hold():
        async with holder.acquire("k"):
            holding.set()
            await release.wait()

    holder_task = asyncio.create_task(hold())
    await holding.wait()

    async def wait_for_lock():
        async with waiter.acquire("k"):
            pass

    waiter_task = asyncio.create_task(wait_for_lock())

    def retry_delays():
        # heartbeat holder'а тоже дёргает patched asyncio.sleep (интервал ttl/3=3.33,
        # без джиттера) — отсеиваем его по величине, нас интересуют только retry-паузы
        return [d for d in delays if d < 1]

    while len(retry_delays()) < 5:
        await real_sleep(0.001)

    release.set()
    await holder_task
    await waiter_task

    delays_seen = retry_delays()
    assert len(set(delays_seen)) > 1  # не константа — джиттер применяется
    lo, hi = 0.02 * 0.5, 0.02 * 1.5
    assert all(lo <= d <= hi for d in delays_seen)


async def test_token_unique_per_acquire():
    r = fakeredis.aioredis.FakeRedis()
    reg = RedisLockRegistry(r, ttl=5, retry_interval=0.01)
    tokens = []
    for _ in range(2):
        async with reg.acquire("k"):
            tokens.append(await r.get("vkd:lock:k"))
    assert tokens[0] != tokens[1]


async def test_reentrant_same_task_does_not_double_lock_redis():
    r = fakeredis.aioredis.FakeRedis()
    reg = RedisLockRegistry(r, ttl=30, retry_interval=0.01)
    async with reg.acquire("k"):
        val1 = await r.get("vkd:lock:k")
        async with reg.acquire("k"):  # реентерабельно — не должно зависнуть/переброситься
            val2 = await r.get("vkd:lock:k")
        assert val2 == val1  # токен не менялся — второго SET не было
    assert await r.get("vkd:lock:k") is None
