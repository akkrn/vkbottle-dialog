from __future__ import annotations

from collections.abc import Callable
from typing import Any

from magic_filter import MagicFilter

from ...exceptions import DialogConfigError
from ..common import Whenable, WhenCondition


class Text(Whenable):
    async def render_text(self, data: dict, manager: Any) -> str:
        if not self.is_(data, manager):
            return ""
        return await self._render_text(data, manager)

    async def _render_text(self, data: dict, manager: Any) -> str:
        raise NotImplementedError

    def __add__(self, other: Text) -> Multi:
        return Multi(self, other, sep="")

    def __or__(self, other: Text) -> Or:
        return Or(self, other)


class Const(Text):
    def __init__(self, text: str, when: WhenCondition = None) -> None:
        super().__init__(when)
        self._text = text

    async def _render_text(self, data: dict, manager: Any) -> str:
        return self._text


class Format(Text):
    def __init__(self, template: str, when: WhenCondition = None) -> None:
        super().__init__(when)
        self._template = template

    async def _render_text(self, data: dict, manager: Any) -> str:
        try:
            return self._template.format_map(data)
        except KeyError as e:
            raise DialogConfigError(
                f"Format({self._template!r}): нет ключа {e} в данных геттеров"
            ) from e


class Multi(Text):
    def __init__(self, *texts: Text, sep: str = "\n", when: WhenCondition = None) -> None:
        super().__init__(when)
        self._texts = texts
        self._sep = sep

    async def _render_text(self, data: dict, manager: Any) -> str:
        parts = [await t.render_text(data, manager) for t in self._texts]
        return self._sep.join(p for p in parts if p)


class Or(Text):
    def __init__(self, *texts: Text, when: WhenCondition = None) -> None:
        super().__init__(when)
        self._texts = texts

    async def _render_text(self, data: dict, manager: Any) -> str:
        for t in self._texts:
            rendered = await t.render_text(data, manager)
            if rendered:
                return rendered
        return ""


Selector = str | MagicFilter | Callable[[dict, "Case", Any], Any]


class Case(Text):
    def __init__(
        self, texts: dict[Any, Text], selector: Selector, when: WhenCondition = None
    ) -> None:
        super().__init__(when)
        self._texts = texts
        self._selector = selector

    def _select(self, data: dict, manager: Any) -> Any:
        if isinstance(self._selector, str):
            return data.get(self._selector)
        if isinstance(self._selector, MagicFilter):
            return self._selector.resolve(data)
        return self._selector(data, self, manager)

    async def _render_text(self, data: dict, manager: Any) -> str:
        key = self._select(data, manager)
        try:
            widget = self._texts.get(key, self._texts.get(...))
        except TypeError:
            raise DialogConfigError(
                f"Case: селектор вернул нехэшируемое значение {key!r}"
            ) from None
        return await widget.render_text(data, manager) if widget else ""
