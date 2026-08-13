from datetime import date

from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import (
    Calendar,
    CalendarConfig,
    CalendarScope,
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


async def test_year_shift_overflow_returns_false_no_crash(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    assert await cal.process_callback(f"cal:y:{10**18}", m) is False


async def test_zoom_months_overflow_returns_false_no_crash(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    assert await cal.process_callback("cal:z:months:99999999999", m) is False


async def test_zoom_days_overflow_returns_false_no_crash(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    assert await cal.process_callback("cal:z:days:99999999999-01", m) is False


async def test_year_shift_clamped_at_min_date_is_silent_noop(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    managed = cal.managed(m)
    managed.set_offset(date(1905, 6, 1))
    assert await cal.process_callback("cal:y:-6", m) is True
    assert managed.get_offset() == date(1905, 6, 1)


async def test_months_per_page_paginates_custom_page_size(fake_manager_factory):
    cfg = CalendarConfig(today=lambda: date(2026, 8, 12), months_per_page=4)
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=cfg)
    await cal.process_callback("cal:z:months", m)

    kb = await cal.render_keyboard({}, m)
    assert sum(len(r) for r in kb) == 8  # 3 nav + 4 months + 1 ⋯
    month_labels = [b.label for row in kb[1:-1] for b in row]
    assert month_labels == ["Янв", "Фев", "Мар", "Апр"]

    more = next(b for row in kb for b in row if ":p:" in (b.callback_data or ""))
    assert await cal.process_callback(more.callback_data, m) is True
    kb2 = await cal.render_keyboard({}, m)
    month_labels2 = [b.label for row in kb2[1:-1] for b in row]
    assert month_labels2 == ["Май", "Июн", "Июл", "Авг"]

    more2 = next(b for row in kb2 for b in row if ":p:" in (b.callback_data or ""))
    await cal.process_callback(more2.callback_data, m)
    kb3 = await cal.render_keyboard({}, m)
    month_labels3 = [b.label for row in kb3[1:-1] for b in row]
    assert month_labels3 == ["Сен", "Окт", "Ноя", "Дек"]

    more3 = next(b for row in kb3 for b in row if ":p:" in (b.callback_data or ""))
    await cal.process_callback(more3.callback_data, m)
    kb4 = await cal.render_keyboard({}, m)
    month_labels4 = [b.label for row in kb4[1:-1] for b in row]
    assert month_labels4 == ["Янв", "Фев", "Мар", "Апр"]  # цикл вернулся на 1 страницу


async def test_months_per_page_default_unchanged(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    await cal.process_callback("cal:z:months", m)
    kb = await cal.render_keyboard({}, m)
    assert sum(len(r) for r in kb) == 10  # 3 nav + 6 months + 1 ⋯, как раньше


async def test_zoom_days_clamped_at_min_max_is_silent_noop(fake_manager_factory):
    cfg = CalendarConfig(
        min_date=date(2026, 1, 1),
        max_date=date(2026, 12, 31),
        today=lambda: date(2026, 8, 1),
    )
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=cfg)
    managed = cal.managed(m)
    # начальное состояние 2026-08-01 (today)
    assert managed.get_offset() == date(2026, 8, 1)
    # попытка перейти в 2000 → clamped, no-op
    assert await cal.process_callback("cal:z:days:2000-06", m) is True
    assert managed.get_offset() == date(2026, 8, 1)
    # попытка перейти в 2050 → clamped, no-op
    assert await cal.process_callback("cal:z:months:2050", m) is True
    assert managed.get_offset() == date(2026, 8, 1)
    # валидный переход
    assert await cal.process_callback("cal:z:days:2026-06", m) is True
    assert managed.get_offset() == date(2026, 6, 1)
