from datetime import date

import pytest

from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import Calendar, CalendarConfig, CalendarLayout
from vkbottle_dialog.widgets.markup import InlineKeyboardFactory, TextKeyboardFactory


class SG(StatesGroup):
    a = State()


CFG = CalendarConfig(today=lambda: date(2026, 8, 12))  # август: 31 день


async def test_wide_renders_whole_month_within_text_limits(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG, layout=CalendarLayout.WIDE)
    kb = await cal.render_keyboard({}, m)
    total = sum(len(r) for r in kb)
    assert total == 3 + 31  # nav + все дни
    assert all(len(r) <= 5 for r in kb)
    assert len(kb) <= 10
    # проходит text-фабрику и НЕ проходит inline
    TextKeyboardFactory().render(kb, "IntentIdAb1", None)
    with pytest.raises(DialogConfigError):
        InlineKeyboardFactory().render(kb, "IntentIdAb1", None)


async def test_compact_passes_inline_factory(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    cal = Calendar(id="cal", config=CFG)
    kb = await cal.render_keyboard({}, m)
    InlineKeyboardFactory().render(kb, "IntentIdAb1", None)  # не падает
