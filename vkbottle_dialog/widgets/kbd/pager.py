from __future__ import annotations

from typing import Any

from ..common import WhenCondition
from ..text.base import Const, Format, Text
from .base import Keyboard, RawKeyboard, VKButton


class BasePager(Keyboard):
    def __init__(self, scroll_id: str, id: str, when: WhenCondition = None) -> None:
        super().__init__(id, when)
        self._scroll_id = scroll_id

    def _scroll(self, manager: Any):
        return manager.find_scroll(self._scroll_id)

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        try:
            page = int(item)
        except ValueError:
            return False
        scroll = self._scroll(manager)
        data = await manager.load_data() if hasattr(manager, "load_data") else {}
        pages = await scroll.get_page_count(data, manager)
        await scroll.set_page(manager, max(0, min(page, pages - 1)))
        return True

    def _btn(self, label: str, page: int) -> VKButton:
        return VKButton(action="callback", label=label, callback_data=f"{self.widget_id}:{page}")


class NumberedPager(BasePager):
    default_page_text: Text = Format("{page}")
    default_current_page_text: Text = Format("[{page}]")

    def __init__(
        self,
        scroll_id: str,
        id: str = "__pager__",
        page_text: Text | None = None,
        current_page_text: Text | None = None,
        when: WhenCondition = None,
    ) -> None:
        super().__init__(scroll_id, id, when)
        self._page_text = page_text or self.default_page_text
        self._current_page_text = current_page_text or self.default_current_page_text

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        scroll = self._scroll(manager)
        pages = await scroll.get_page_count(data, manager)
        current = scroll.get_page(manager)
        row = []
        for page in range(pages):
            text = self._current_page_text if page == current else self._page_text
            label = await text.render_text({"page": page + 1, **data}, manager)
            row.append(self._btn(label, page))
        return [row] if pages > 1 else []


class _JumpPager(BasePager):
    default_text: Text = Const("")

    def __init__(
        self, scroll_id: str, id: str, text: Text | None = None, when: WhenCondition = None
    ) -> None:
        super().__init__(scroll_id, id, when)
        self._text = text or self.default_text

    def _target(self, current: int, pages: int) -> int:
        raise NotImplementedError

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        scroll = self._scroll(manager)
        pages = await scroll.get_page_count(data, manager)
        current = scroll.get_page(manager)
        label = await self._text.render_text(
            {"page": current + 1, "pages": pages, **data}, manager
        )
        return [[self._btn(label, self._target(current, pages))]]


class NextPage(_JumpPager):
    default_text = Const("›")

    def __init__(self, scroll_id: str, id: str = "__next_p__", **kw) -> None:
        super().__init__(scroll_id, id, **kw)

    def _target(self, current: int, pages: int) -> int:
        return min(pages - 1, current + 1)


class PrevPage(_JumpPager):
    default_text = Const("‹")

    def __init__(self, scroll_id: str, id: str = "__prev_p__", **kw) -> None:
        super().__init__(scroll_id, id, **kw)

    def _target(self, current: int, pages: int) -> int:
        return max(0, current - 1)


class FirstPage(_JumpPager):
    default_text = Const("«")

    def __init__(self, scroll_id: str, id: str = "__first_p__", **kw) -> None:
        super().__init__(scroll_id, id, **kw)

    def _target(self, current: int, pages: int) -> int:
        return 0


class LastPage(_JumpPager):
    default_text = Const("»")

    def __init__(self, scroll_id: str, id: str = "__last_p__", **kw) -> None:
        super().__init__(scroll_id, id, **kw)

    def _target(self, current: int, pages: int) -> int:
        return pages - 1


class CurrentPage(_JumpPager):
    default_text = Format("{page}/{pages}")

    def __init__(self, scroll_id: str, id: str = "__cur_p__", **kw) -> None:
        super().__init__(scroll_id, id, **kw)

    def _target(self, current: int, pages: int) -> int:
        return current


class SwitchPage(_JumpPager):
    def __init__(self, scroll_id: str, id: str, page: int, text: Text, **kw) -> None:
        super().__init__(scroll_id, id, text=text, **kw)
        self._page = page

    def _target(self, current: int, pages: int) -> int:
        return max(0, min(self._page, pages - 1))
