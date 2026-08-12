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
    WIDE = "wide"


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


class VKCalendarDaysView:
    def __init__(
        self,
        date_text: Text | None = None,
        header_text: Text | None = None,
        prev_text: Text | None = None,
        next_text: Text | None = None,
        more_text: Text | None = None,
    ) -> None:
        self.date_text = date_text or _DEFAULT_DATE_TEXT
        self.header_text = header_text or Format("{month} {year}")
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
        per_page = config.days_per_page
        pages = math.ceil(total_days / per_page)
        page = min(page, pages - 1)
        start = page * per_page
        row: list[VKButton] = []
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
        return {CalendarScope.DAYS: VKCalendarDaysView()}
        # задачи 5-6 добавят MONTHS/YEARS и WIDE-вариант DAYS

    async def _get_user_config(self, data: dict, manager: Any) -> CalendarUserConfig:
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
            self._set_state(manager, scope, _shift_month(offset, delta), 0)
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
        # Задача 5 наполняет переходы; в задаче 4 z:months сохраняет scope
        # MONTHS (вьюха появится в задаче 5) — здесь возвращаем True, но
        # состояние не меняем, чтобы рендер не упал без вьюхи.
        return True

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
