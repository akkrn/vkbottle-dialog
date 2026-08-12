from datetime import time

from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import ButtonColor, TimeSelect


class SG(StatesGroup):
    a = State()


async def test_render_first_page_and_limits(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    ts = TimeSelect(id="ts")  # шаг 30 мин → 48 слотов, 6 страниц
    kb = await ts.render_keyboard({}, m)
    assert sum(len(r) for r in kb) == 10 and len(kb) == 3
    assert kb[0][0].label == "00:00" and kb[0][0].callback_data == "ts:t:00:00"
    assert [b.callback_data for b in kb[2]] == ["ts:p:0", "ts:p:1"]  # ‹ кламп


async def test_pagination_clamped(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    ts = TimeSelect(id="ts")
    await ts.process_callback("ts:p:99", m)  # кламп на последнюю (5)
    kb = await ts.render_keyboard({}, m)
    assert kb[0][0].label == "20:00"  # слоты 40..47 → 20:00..23:30


async def test_select_and_managed(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    changed = []

    async def on_value_changed(event, managed, manager, value):
        changed.append(value)

    ts = TimeSelect(id="ts", on_value_changed=on_value_changed)
    assert await ts.process_callback("ts:t:12:30", m) is True
    assert changed == [time(12, 30)]
    managed = ts.managed(m)
    assert managed.get_value() == time(12, 30)
    kb = await ts.render_keyboard({}, m)
    # выбранный слот подсвечен на своей странице
    await ts.process_callback("ts:p:1", m)
    kb = await ts.render_keyboard({}, m)
    # страница 1: 04:00..07:30 — выбранного нет, цвета нет
    assert all(b.color is not ButtonColor.POSITIVE for b in kb[0] + kb[1])


async def test_broken_items(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    ts = TimeSelect(id="ts", minute_precision=30)
    assert await ts.process_callback("ts:t:25:99", m) is False
    assert await ts.process_callback("ts:t:12:07", m) is False  # мимо сетки шага
    assert await ts.process_callback("ts:p:x", m) is False
