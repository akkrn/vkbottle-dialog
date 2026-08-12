from datetime import date

from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import (
    Calendar, CalendarConfig, CalendarScope,
)


class SG(StatesGroup):
    a = State()


CFG = CalendarConfig(today=lambda: date(2026, 8, 12))


async def test_zoom_to_months_and_render(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    await cal.process_callback("cal:z:months", m)
    assert cal.managed(m).get_scope() is CalendarScope.MONTHS
    kb = await cal.render_keyboard({}, m)
    assert sum(len(r) for r in kb) == 10
    assert kb[0][1].label == "2026" and kb[0][1].callback_data == "cal:z:years"
    assert kb[1][0].label == "Янв"
    assert kb[1][0].callback_data == "cal:z:days:2026-01"


async def test_month_click_returns_to_days(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    await cal.process_callback("cal:z:months", m)
    await cal.process_callback("cal:z:days:2026-03", m)
    managed = cal.managed(m)
    assert managed.get_scope() is CalendarScope.DAYS
    assert managed.get_offset() == date(2026, 3, 1)


async def test_years_scope_and_navigation(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    await cal.process_callback("cal:z:months", m)
    await cal.process_callback("cal:z:years", m)
    kb = await cal.render_keyboard({}, m)
    assert sum(len(r) for r in kb) == 9  # 3 nav + 6 лет
    year_labels = [b.label for b in kb[1] + kb[2]]
    assert "2026" in year_labels
    await cal.process_callback("cal:y:+6", m)
    kb2 = await cal.render_keyboard({}, m)
    year_labels2 = [b.label for b in kb2[1] + kb2[2]]
    assert year_labels2 != year_labels
    # клик года → MONTHS этого года
    await cal.process_callback("cal:z:months:2031", m)
    managed = cal.managed(m)
    assert managed.get_scope() is CalendarScope.MONTHS
    assert managed.get_offset().year == 2031


async def test_noop_and_broken_zoom(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    assert await cal.process_callback("cal:noop", m) is True
    assert await cal.process_callback("cal:z:bogus", m) is False
    assert await cal.process_callback("cal:z:days:20xx-99", m) is False
