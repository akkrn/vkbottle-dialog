import fakeredis.aioredis
import pytest

from vkbottle_dialog.context.memory import MemoryStorage
from vkbottle_dialog.context.redis import RedisStorage


@pytest.fixture(params=["memory", "redis"])
def storage(request):
    if request.param == "memory":
        return MemoryStorage()
    return RedisStorage(fakeredis.aioredis.FakeRedis(), ttl=60)


async def test_roundtrip(storage):
    assert await storage.get("k") is None
    await storage.set("k", {"a": [1, "б"]})
    assert await storage.get("k") == {"a": [1, "б"]}
    await storage.delete("k")
    assert await storage.get("k") is None


async def test_touch_does_not_fail(storage):
    await storage.set("k", {"a": 1})
    await storage.touch("k", "missing")
    assert await storage.get("k") == {"a": 1}


async def test_redis_sets_ttl():
    r = fakeredis.aioredis.FakeRedis()
    st = RedisStorage(r, ttl=60)
    await st.set("k", {"a": 1})
    assert 0 < await r.ttl("k") <= 60
