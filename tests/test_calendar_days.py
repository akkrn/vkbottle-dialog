from datetime import date

from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd.calendar import (
    Calendar,
    CalendarConfig,
    CalendarUserConfig,
)


class SG(StatesGroup):
    a = State()


CFG = CalendarConfig(today=lambda: date(2026, 8, 12))


def flat(kb):
    return [(b.label, b.callback_data) for row in kb for b in row]


async def test_days_compact_layout_and_limits(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    kb = await cal.render_keyboard({}, m)
    assert len(kb) == 4  # nav + 2 строки дней + ⋯
    assert sum(len(r) for r in kb) == 10  # ровно лимит inline
    assert all(len(r) <= 5 for r in kb)
    nav = kb[0]
    assert nav[0].callback_data == "cal:m:-1"
    assert nav[1].label == "Август 2026" and nav[1].callback_data == "cal:z:months"
    assert nav[2].callback_data == "cal:m:+1"
    assert kb[1][0].callback_data == "cal:d:2026-08-01"
    assert kb[3][0].callback_data == "cal:p:1"  # ⋯ на вторую страницу


async def test_days_pagination_cycles(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    # Август: 31 день, по 6 → 6 страниц (последняя: 31)
    for _ in range(5):
        page = cal._get_state(m)[2]
        await cal.process_callback(f"cal:p:{page + 1}", m)
    kb = await cal.render_keyboard({}, m)
    labels = [b.label for b in kb[1]]
    assert "31" in labels
    assert kb[-1][0].callback_data == "cal:p:0"  # цикл на первую


async def test_month_shift(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    await cal.process_callback("cal:m:+1", m)
    scope, offset, page = cal._get_state(m)
    assert offset == date(2026, 9, 1) and page == 0
    await cal.process_callback("cal:m:-1", m)
    assert cal._get_state(m)[1] == date(2026, 8, 1)


async def test_date_click_and_validation(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    picked = []

    async def on_click(event, managed, manager, selected):
        picked.append(selected)

    cfg = CalendarConfig(today=lambda: date(2026, 8, 12), min_date=date(2026, 8, 5))
    cal = Calendar(id="cal", config=cfg, on_click=on_click)
    assert await cal.process_callback("cal:d:2026-08-10", m) is True
    assert picked == [date(2026, 8, 10)]
    assert await cal.process_callback("cal:d:2026-08-01", m) is False  # < min
    assert await cal.process_callback("cal:d:not-a-date", m) is False
    assert picked == [date(2026, 8, 10)]  # битые клики без колбэков


async def test_user_config_merge(fake_manager_factory):
    merged = CFG.merge(CalendarUserConfig(min_date=date(2000, 1, 1)))
    assert merged.min_date == date(2000, 1, 1)
    assert merged.max_date == CFG.max_date
