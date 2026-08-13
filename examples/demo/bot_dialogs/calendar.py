"""Секция «Календарь»: Calendar (по умолчанию и кастомный сабкласс) и
TimeSelect показывают выбор даты/времени клавиатурой.

Бюджет клавиатуры (нормативная таблица §2 дизайн-документа) ограничивает
демо: Calendar — days_per_page=3 (3 дня на страницу вместо целой недели),
TimeSelect — hour_range=(10, 14) (полдня вместо суток). В тексте окон это
поясняется отдельно."""

from __future__ import annotations

from datetime import date, time
from typing import Any

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.kbd import (
    Calendar,
    CalendarConfig,
    CalendarScope,
    Group,
    SwitchTo,
    TimeSelect,
)
from vkbottle_dialog.widgets.kbd.calendar import VKCalendarDaysView
from vkbottle_dialog.widgets.text import Const, Format

from .common import MAIN_MENU_BUTTON, nav_row
from .states import CalendarSG

DEMO_CAL_CONFIG = CalendarConfig(days_per_page=3, months_per_page=4, years_per_page=4)


async def on_date_click(event, managed, manager, selected: date) -> None:
    await manager.answer(snackbar=f"Выбрано: {selected.isoformat()}")


async def on_time_click(event, managed, manager, selected: time) -> None:
    await manager.answer(snackbar=f"Время: {selected.strftime('%H:%M')}")


def _is_selected(data: dict, widget: Any, manager: Any) -> bool:
    """`data` здесь — scoped-словарь ячейки VKCalendarDaysView
    ({"data": <данные окна>, "day": ..., "date": ...}), не данные окна
    напрямую — так дата конкретной ячейки доступна предикату."""
    cell_date = data.get("date")
    if cell_date is None:
        return False
    selected = data.get("data", {}).get("dialog_data", {}).get("selected", [])
    return cell_date.isoformat() in selected


class EmojiCalendar(Calendar):
    """Сабкласс Calendar с кастомными Text-виджетами дней: выбранные даты
    подсвечиваются 🔴, выбор копится в dialog_data["selected"] (список ISO)."""

    def _init_views(self) -> dict[CalendarScope, Any]:
        views = super()._init_views()
        views[CalendarScope.DAYS] = VKCalendarDaysView(
            date_text=Const("🔴", when=_is_selected) | Format("{day}"),
            header_text=Format("✦ {month} {year} ✦"),
        )
        return views


async def on_custom_date_click(event, managed, manager, selected: date) -> None:
    iso = selected.isoformat()
    chosen: list[str] = manager.dialog_data.setdefault("selected", [])
    if iso in chosen:
        chosen.remove(iso)
    else:
        chosen.append(iso)
    await manager.answer(snackbar=f"Выбрано дат: {len(chosen)}")


def custom_calendar_getter(dialog_manager, **kwargs) -> dict:
    selected = dialog_manager.dialog_data.get("selected", [])
    return {"selected_str": ", ".join(selected)} if selected else {}


MAIN_WINDOW = Window(
    Const("📅 Календарь: Calendar / TimeSelect"),
    Const("Выберите подсекцию:"),
    Group(
        SwitchTo(Const("По умолчанию"), id="to_default", state=CalendarSG.DEFAULT),
        SwitchTo(Const("Кастомный"), id="to_custom", state=CalendarSG.CUSTOM),
        SwitchTo(Const("Время"), id="to_time", state=CalendarSG.TIME),
        MAIN_MENU_BUTTON,
        width=2,
    ),
    state=CalendarSG.MAIN,
)

DEFAULT_WINDOW = Window(
    Const("Calendar — стандартный выбор даты, клик по дню шлёт снекбар."),
    Const(
        "Демо-бюджет клавиатуры показывает по 3 дня на странице "
        "(days_per_page=3), листайте «⋯» до нужной даты — в реальном "
        "боте без ограничения кнопок навигации можно показывать всю неделю."
    ),
    Calendar(id="cal", config=DEMO_CAL_CONFIG, on_click=on_date_click),
    nav_row(CalendarSG.MAIN),
    state=CalendarSG.DEFAULT,
)

CUSTOM_WINDOW = Window(
    Const("Кастомный календарь — сабкласс Calendar со своими Text-виджетами."),
    Const("Клик по дню тогглит выбор (🔴), можно отметить сразу несколько дат."),
    Format("Выбрано: {selected_str}", when="selected_str"),
    EmojiCalendar(id="cal_custom", config=DEMO_CAL_CONFIG, on_click=on_custom_date_click),
    nav_row(CalendarSG.MAIN),
    state=CalendarSG.CUSTOM,
    getter=custom_calendar_getter,
)

TIME_WINDOW = Window(
    Const("TimeSelect — выбор времени с шагом minute_precision."),
    Const(
        "Демо-бюджет ограничивает диапазон 10:00–14:00 (hour_range=(10, 14)) "
        "с шагом 30 минут — 8 слотов на одной странице, без ‹›. Полный день "
        "— уберите строку навигации из бюджета."
    ),
    TimeSelect(id="time", hour_range=(10, 14), minute_precision=30, on_click=on_time_click),
    nav_row(CalendarSG.MAIN),
    state=CalendarSG.TIME,
)

calendar_dialog = Dialog(MAIN_WINDOW, DEFAULT_WINDOW, CUSTOM_WINDOW, TIME_WINDOW)
