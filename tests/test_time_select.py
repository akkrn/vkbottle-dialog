from datetime import time

import pytest

from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import ButtonColor, TimeSelect


class SG(StatesGroup):
    a = State()


def test_invalid_minute_precision_rejected():
    with pytest.raises(DialogConfigError):
        TimeSelect(id="ts", minute_precision=0)
    with pytest.raises(DialogConfigError):
        TimeSelect(id="ts", minute_precision=61)


def test_invalid_hour_range_rejected():
    with pytest.raises(DialogConfigError):
        TimeSelect(id="ts", hour_range=(10, 10))
    with pytest.raises(DialogConfigError):
        TimeSelect(id="ts", hour_range=(12, 5))


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


async def test_single_page_no_nav(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    ts = TimeSelect(id="ts", hour_range=(9, 10), minute_precision=30)
    kb = await ts.render_keyboard({}, m)
    # hour_range=(9,10) with precision=30 → 2 slots: 09:00, 09:30
    # 2 slots fit in 1 page (page size = 8), so no nav row
    assert len(kb) == 1  # only the slots row, no nav
    assert [b.label for b in kb[0]] == ["09:00", "09:30"]


async def test_set_value_snapping_and_highlight(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    ts = TimeSelect(id="ts", minute_precision=30)
    managed = ts.managed(m)
    # set_value with off-grid time (13:07) should snap to nearest valid slot
    managed.set_value(time(13, 7))
    result = managed.get_value()
    # 13:07 is 787 minutes; nearest slots are 13:00 (780) and 13:30 (810)
    # distance to 13:00 = 7, distance to 13:30 = 23, so should snap to 13:00
    assert result == time(13, 0)
    # navigate to page 3 where 13:00 is (slots 24-31)
    await ts.process_callback("ts:p:3", m)
    # verify the keyboard highlights the snapped slot
    kb = await ts.render_keyboard({}, m)
    highlighted = [b for row in kb for b in row if b.color == ButtonColor.POSITIVE]
    assert len(highlighted) == 1
    assert highlighted[0].label == "13:00"


async def test_repeat_click_callbacks(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    click_events = []
    value_change_events = []

    async def on_click(event, managed, manager, value):
        click_events.append(value)

    async def on_value_changed(event, managed, manager, value):
        value_change_events.append(value)

    ts = TimeSelect(id="ts", on_click=on_click, on_value_changed=on_value_changed)
    # first click: both callbacks fire
    await ts.process_callback("ts:t:12:30", m)
    assert click_events == [time(12, 30)]
    assert value_change_events == [time(12, 30)]
    # repeat click on same slot: on_click fires, on_value_changed does NOT
    await ts.process_callback("ts:t:12:30", m)
    assert click_events == [time(12, 30), time(12, 30)]
    assert value_change_events == [time(12, 30)]  # no change event
