from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Any

from ..common import WhenCondition, ensure_event_processor
from ..text.base import Const, Format, Text
from .base import Keyboard, RawKeyboard, VKButton

RU_MONTHS = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)
RU_MONTHS_SHORT = (
    "Янв",
    "Фев",
    "Мар",
    "Апр",
    "Май",
    "Июн",
    "Июл",
    "Авг",
    "Сен",
    "Окт",
    "Ноя",
    "Дек",
)
RU_WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


class CalendarScope(str, Enum):
    DAYS = "days"
    MONTHS = "months"
    YEARS = "years"


class CalendarLayout(str, Enum):
    COMPACT = "compact"
    WIDE = "wide"  # DM-only; full month; raises DialogConfigError in chats


@dataclass
class CalendarUserConfig:
    firstweekday: int | None = None
    min_date: date | None = None
    max_date: date | None = None


@dataclass
class CalendarConfig:
    min_date: date = date(1900, 1, 1)
    max_date: date = date(2100, 1, 1)
    firstweekday: int = 0
    month_names: Sequence[str] = RU_MONTHS
    month_short_names: Sequence[str] = RU_MONTHS_SHORT
    weekday_names: Sequence[str] = RU_WEEKDAYS
    years_per_page: int = 6
    days_per_page: int = 6
    months_per_page: int = 6
    today: Callable[[], date] = date.today

    def merge(self, user: CalendarUserConfig) -> CalendarConfig:
        changes = {k: v for k, v in vars(user).items() if v is not None}
        return replace(self, **changes) if changes else self


def _days_in_month(offset: date) -> int:
    import calendar as _cal  # stdlib, имя занято нашим модулем

    return _cal.monthrange(offset.year, offset.month)[1]


def _shift_month(offset: date, delta: int) -> date:
    month0 = offset.year * 12 + (offset.month - 1) + delta
    return date(month0 // 12, month0 % 12 + 1, 1)


_DEFAULT_DATE_TEXT = Format("{day}")
_DEFAULT_PREV_TEXT = Const("‹")
_DEFAULT_NEXT_TEXT = Const("›")
_DEFAULT_MORE_TEXT = Const("⋯")
_DEFAULT_MONTH_TEXT = Format("{month}")
_DEFAULT_HEADER_TEXT_MONTHS = Format("{year}")
_DEFAULT_HEADER_TEXT_YEARS = Format("{first}–{last}")
_DEFAULT_YEAR_TEXT = Format("{year}")


class VKCalendarMonthsView:
    def __init__(
        self,
        month_text: Text | None = None,
        header_text: Text | None = None,
        prev_text: Text | None = None,
        next_text: Text | None = None,
        more_text: Text | None = None,
    ) -> None:
        self.month_text = month_text or _DEFAULT_MONTH_TEXT
        self.header_text = header_text or _DEFAULT_HEADER_TEXT_MONTHS
        self.prev_text = prev_text or _DEFAULT_PREV_TEXT
        self.next_text = next_text or _DEFAULT_NEXT_TEXT
        self.more_text = more_text or _DEFAULT_MORE_TEXT

    async def render(
        self,
        data: dict,
        manager: Any,
        calendar: Calendar,
        config: CalendarConfig,
        offset: date,
        page: int,
    ) -> RawKeyboard:
        wid = calendar.widget_id
        scope_data = {"data": data, "year": offset.year}
        kb: RawKeyboard = [
            [
                VKButton(
                    "callback",
                    await self.prev_text.render_text(scope_data, manager),
                    f"{wid}:y:-1",
                ),
                VKButton(
                    "callback",
                    await self.header_text.render_text(scope_data, manager),
                    f"{wid}:z:years",
                ),
                VKButton(
                    "callback",
                    await self.next_text.render_text(scope_data, manager),
                    f"{wid}:y:+1",
                ),
            ]
        ]
        per_page = config.months_per_page
        pages = math.ceil(12 / per_page)
        page = page % pages
        start = page * per_page
        row: list[VKButton] = []
        for idx in range(start, min(start + per_page, 12)):
            scoped = {"data": data, "month": config.month_short_names[idx], "year": offset.year}
            row.append(
                VKButton(
                    "callback",
                    await self.month_text.render_text(scoped, manager),
                    f"{wid}:z:days:{offset.year}-{idx + 1:02d}",
                )
            )
            if len(row) == 3:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        if pages > 1:
            kb.append(
                [
                    VKButton(
                        "callback",
                        await self.more_text.render_text(scope_data, manager),
                        f"{wid}:p:{(page + 1) % pages}",
                    )
                ]
            )
        return kb


class VKCalendarYearsView:
    def __init__(
        self,
        year_text: Text | None = None,
        header_text: Text | None = None,
        prev_text: Text | None = None,
        next_text: Text | None = None,
    ) -> None:
        self.year_text = year_text or _DEFAULT_YEAR_TEXT
        self.header_text = header_text or _DEFAULT_HEADER_TEXT_YEARS
        self.prev_text = prev_text or _DEFAULT_PREV_TEXT
        self.next_text = next_text or _DEFAULT_NEXT_TEXT

    async def render(
        self,
        data: dict,
        manager: Any,
        calendar: Calendar,
        config: CalendarConfig,
        offset: date,
        page: int,
    ) -> RawKeyboard:
        wid = calendar.widget_id
        per_page = config.years_per_page
        first = offset.year - offset.year % per_page
        scope_data = {"data": data, "first": first, "last": first + per_page - 1}
        kb: RawKeyboard = [
            [
                VKButton(
                    "callback",
                    await self.prev_text.render_text(scope_data, manager),
                    f"{wid}:y:-{per_page}",
                ),
                VKButton(
                    "callback",
                    await self.header_text.render_text(scope_data, manager),
                    f"{wid}:noop",
                ),
                VKButton(
                    "callback",
                    await self.next_text.render_text(scope_data, manager),
                    f"{wid}:y:+{per_page}",
                ),
            ]
        ]
        row: list[VKButton] = []
        for year in range(first, first + per_page):
            scoped = {"data": data, "year": year}
            row.append(
                VKButton(
                    "callback",
                    await self.year_text.render_text(scoped, manager),
                    f"{wid}:z:months:{year}",
                )
            )
            if len(row) == 3:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        return kb


class VKCalendarDaysView:
    def __init__(
        self,
        date_text: Text | None = None,
        header_text: Text | None = None,
        prev_text: Text | None = None,
        next_text: Text | None = None,
        more_text: Text | None = None,
        wide: bool = False,
    ) -> None:
        self.date_text = date_text or _DEFAULT_DATE_TEXT
        self.header_text = header_text or Format("{month} {year}")
        self.prev_text = prev_text or _DEFAULT_PREV_TEXT
        self.next_text = next_text or _DEFAULT_NEXT_TEXT
        self.more_text = more_text or _DEFAULT_MORE_TEXT
        self.wide = wide

    async def render(
        self,
        data: dict,
        manager: Any,
        calendar: Calendar,
        config: CalendarConfig,
        offset: date,
        page: int,
    ) -> RawKeyboard:
        wid = calendar.widget_id
        header_scope = {
            "data": data,
            "month": config.month_names[offset.month - 1],
            "year": offset.year,
            "date": offset,
        }
        kb: RawKeyboard = [
            [
                VKButton(
                    "callback",
                    await self.prev_text.render_text(header_scope, manager),
                    f"{wid}:m:-1",
                ),
                VKButton(
                    "callback",
                    await self.header_text.render_text(header_scope, manager),
                    f"{wid}:z:months",
                ),
                VKButton(
                    "callback",
                    await self.next_text.render_text(header_scope, manager),
                    f"{wid}:m:+1",
                ),
            ]
        ]
        total_days = _days_in_month(offset)
        if self.wide:
            row: list[VKButton] = []
            for day in range(1, total_days + 1):
                d = date(offset.year, offset.month, day)
                scoped = {"data": data, "day": day, "date": d}
                row.append(
                    VKButton(
                        "callback",
                        await self.date_text.render_text(scoped, manager),
                        f"{wid}:d:{d.isoformat()}",
                    )
                )
                if len(row) == 5:
                    kb.append(row)
                    row = []
            if row:
                kb.append(row)
            return kb
        per_page = config.days_per_page
        pages = math.ceil(total_days / per_page)
        page = min(page, pages - 1)
        start = page * per_page
        row = []
        for day in range(start + 1, min(start + per_page, total_days) + 1):
            d = date(offset.year, offset.month, day)
            scoped = {"data": data, "day": day, "date": d}
            row.append(
                VKButton(
                    "callback",
                    await self.date_text.render_text(scoped, manager),
                    f"{wid}:d:{d.isoformat()}",
                )
            )
            if len(row) == 3:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        if pages > 1:
            kb.append(
                [
                    VKButton(
                        "callback",
                        await self.more_text.render_text(header_scope, manager),
                        f"{wid}:p:{(page + 1) % pages}",
                    )
                ]
            )
        return kb


class Calendar(Keyboard):
    def __init__(
        self,
        id: str,
        on_click: Callable | None = None,
        config: CalendarConfig | None = None,
        layout: CalendarLayout = CalendarLayout.COMPACT,
        when: WhenCondition = None,
    ) -> None:
        super().__init__(id, when)
        self._config = config or CalendarConfig()
        self._layout = layout
        self._on_click = ensure_event_processor(on_click)
        self._views = self._init_views()

    def _init_views(self) -> dict[CalendarScope, Any]:
        return {
            CalendarScope.DAYS: VKCalendarDaysView(wide=(self._layout is CalendarLayout.WIDE)),
            CalendarScope.MONTHS: VKCalendarMonthsView(),
            CalendarScope.YEARS: VKCalendarYearsView(),
        }

    async def _get_user_config(self, data: dict, manager: Any) -> CalendarUserConfig:
        """Merged user config affects RENDER only; click-time validation uses base config."""
        return CalendarUserConfig()

    def _get_state(self, manager: Any) -> tuple[CalendarScope, date, int]:
        raw = self.get_widget_data(manager, None)
        if not raw:
            today = self._config.today()
            return CalendarScope.DAYS, today.replace(day=1), 0
        return (CalendarScope(raw["scope"]), date.fromisoformat(raw["offset"]), int(raw["page"]))

    def _set_state(self, manager: Any, scope: CalendarScope, offset: date, page: int) -> None:
        self.set_widget_data(
            manager, {"scope": scope.value, "offset": offset.isoformat(), "page": page}
        )

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        config = self._config.merge(await self._get_user_config(data, manager))
        scope, offset, page = self._get_state(manager)
        view = self._views[scope]
        return await view.render(data, manager, self, config, offset, page)

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        config = self._config  # клики валидируются базовым конфигом
        scope, offset, page = self._get_state(manager)
        if item == "noop":
            return True
        kind, _, arg = item.partition(":")
        if kind == "d":
            try:
                selected = date.fromisoformat(arg)
            except ValueError:
                return False
            if not (config.min_date <= selected <= config.max_date):
                return False
            await self._on_click.process_event(
                manager.event, self.managed(manager), manager, selected
            )
            return True
        if kind == "m":
            try:
                delta = int(arg)
            except ValueError:
                return False
            try:
                new_offset = _shift_month(offset, delta)
            except (ValueError, OverflowError):
                return False
            if not (config.min_date.replace(day=1) <= new_offset <= config.max_date):
                return True
            self._set_state(manager, scope, new_offset, 0)
            return True
        if kind == "y":
            try:
                delta = int(arg)
            except ValueError:
                return False
            try:
                new_offset = offset.replace(year=offset.year + delta)
            except (ValueError, OverflowError):
                try:
                    # Handle Feb 29 in leap year
                    new_offset = date(offset.year + delta, offset.month, 1)
                except (ValueError, OverflowError):
                    return False
            if not (config.min_date.replace(day=1) <= new_offset <= config.max_date):
                return True
            self._set_state(manager, scope, new_offset, 0)
            return True
        if kind == "p":
            try:
                target = int(arg)
            except ValueError:
                return False
            self._set_state(manager, scope, offset, max(0, target))
            return True
        if kind == "z":
            return await self._process_zoom(arg, manager, offset)
        return False

    async def _process_zoom(self, arg: str, manager: Any, offset: date) -> bool:
        if arg == "months":
            self._set_state(manager, CalendarScope.MONTHS, offset, 0)
            return True
        if arg == "years":
            self._set_state(manager, CalendarScope.YEARS, offset, 0)
            return True
        kind, _, rest = arg.partition(":")
        if kind == "days":
            try:
                year, month = rest.split("-")
                target = date(int(year), int(month), 1)
            except (ValueError, OverflowError):
                return False
            self._set_state(manager, CalendarScope.DAYS, target, 0)
            return True
        if kind == "months":
            try:
                target = date(int(rest), 1, 1)
            except (ValueError, OverflowError):
                return False
            self._set_state(manager, CalendarScope.MONTHS, target, 0)
            return True
        return False

    def managed(self, manager: Any) -> ManagedCalendar:
        return ManagedCalendar(self, manager)


class ManagedCalendar:
    def __init__(self, widget: Calendar, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def get_scope(self) -> CalendarScope:
        return self._widget._get_state(self._manager)[0]

    def get_offset(self) -> date:
        return self._widget._get_state(self._manager)[1]

    def set_scope(self, scope: CalendarScope) -> None:
        _, offset, _ = self._widget._get_state(self._manager)
        self._widget._set_state(self._manager, scope, offset, 0)

    def set_offset(self, offset: date) -> None:
        scope, _, _ = self._widget._get_state(self._manager)
        self._widget._set_state(self._manager, scope, offset, 0)
