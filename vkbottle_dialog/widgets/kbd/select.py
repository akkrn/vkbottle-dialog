from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..common import WhenCondition, ensure_event_processor, get_items_getter
from ..text.base import Text
from .base import Keyboard, RawKeyboard, VKButton


class Select(Keyboard):
    def __init__(self, text: Text, id: str, item_id_getter: Callable[[Any], Any],
                 items: Any, on_click: Callable | None = None,
                 when: WhenCondition = None) -> None:
        super().__init__(id, when)
        self._text = text
        self._item_id_getter = item_id_getter
        self._items = get_items_getter(items)
        self._on_click = ensure_event_processor(on_click)

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        buttons = []
        for pos, item in enumerate(self._items(data)):
            scoped = {"data": data, "item": item, "pos": pos + 1, "pos0": pos}
            buttons.append(VKButton(
                action="callback",
                label=await self._text.render_text(scoped, manager),
                callback_data=f"{self.widget_id}:{self._item_id_getter(item)}",
            ))
        return [[b] for b in buttons]

    async def _process_item_callback(self, item: str, manager: Any) -> bool:
        await self._handle_click(item, manager)
        return True

    async def _handle_click(self, item_id: str, manager: Any) -> None:
        await self._on_click.process_event(manager.event, self, manager, item_id)


class Radio(Select):
    def __init__(self, checked_text: Text, unchecked_text: Text, id: str,
                 item_id_getter: Callable, items: Any, type_factory: Callable = str,
                 on_click: Callable | None = None,
                 on_state_changed: Callable | None = None,
                 when: WhenCondition = None) -> None:
        super().__init__(unchecked_text, id, item_id_getter, items, on_click, when)
        self._checked_text = checked_text
        self._type_factory = type_factory
        self._on_state_changed = ensure_event_processor(on_state_changed)

    def _is_checked(self, item_id: Any, manager: Any) -> bool:
        return str(item_id) == self.get_widget_data(manager, None)

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        buttons = []
        for pos, item in enumerate(self._items(data)):
            item_id = self._item_id_getter(item)
            text = (self._checked_text if self._is_checked(item_id, manager)
                    else self._text)
            scoped = {"data": data, "item": item, "pos": pos + 1, "pos0": pos}
            buttons.append(VKButton(
                action="callback",
                label=await text.render_text(scoped, manager),
                callback_data=f"{self.widget_id}:{item_id}",
            ))
        return [[b] for b in buttons]

    async def _handle_click(self, item_id: str, manager: Any) -> None:
        self.set_widget_data(manager, item_id)
        await self._on_state_changed.process_event(manager.event, self, manager, item_id)
        await self._on_click.process_event(manager.event, self, manager, item_id)

    def managed(self, manager: Any):
        return ManagedRadio(self, manager)


class ManagedRadio:
    def __init__(self, widget: Radio, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def get_checked(self) -> Any:
        raw = self._widget.get_widget_data(self._manager, None)
        return self._widget._type_factory(raw) if raw is not None else None

    def is_checked(self, item_id: Any) -> bool:
        return self._widget._is_checked(item_id, self._manager)

    def set_checked(self, item_id: Any) -> None:
        self._widget.set_widget_data(self._manager, str(item_id))


class Multiselect(Radio):
    def __init__(self, checked_text: Text, unchecked_text: Text, id: str,
                 item_id_getter: Callable, items: Any, min_selected: int = 0,
                 max_selected: int = 0, type_factory: Callable = str,
                 on_click: Callable | None = None,
                 on_state_changed: Callable | None = None,
                 when: WhenCondition = None) -> None:
        super().__init__(checked_text, unchecked_text, id, item_id_getter, items,
                         type_factory, on_click, on_state_changed, when)
        self._min = min_selected
        self._max = max_selected

    def _is_checked(self, item_id: Any, manager: Any) -> bool:
        return str(item_id) in self.get_widget_data(manager, [])

    async def _handle_click(self, item_id: str, manager: Any) -> None:
        checked: list[str] = list(self.get_widget_data(manager, []))
        if item_id in checked:
            if len(checked) <= self._min:
                return  # uncheck blocked by min_selected
            checked.remove(item_id)
        else:
            if self._max != 0 and len(checked) >= self._max:
                return  # check blocked by max_selected
            checked.append(item_id)
        self.set_widget_data(manager, checked)
        await self._on_state_changed.process_event(manager.event, self, manager, item_id)
        await self._on_click.process_event(manager.event, self, manager, item_id)

    def managed(self, manager: Any):
        return ManagedMultiselect(self, manager)


class ManagedMultiselect:
    def __init__(self, widget: Multiselect, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def get_checked(self) -> list:
        return [self._widget._type_factory(i)
                for i in self._widget.get_widget_data(self._manager, [])]

    def is_checked(self, item_id: Any) -> bool:
        return self._widget._is_checked(item_id, self._manager)

    def set_checked(self, item_id: Any, checked: bool) -> None:
        items = list(self._widget.get_widget_data(self._manager, []))
        key = str(item_id)
        if checked and key not in items:
            items.append(key)
        if not checked and key in items:
            items.remove(key)
        self._widget.set_widget_data(self._manager, items)

    def reset_checked(self) -> None:
        self._widget.set_widget_data(self._manager, [])


class Toggle(Keyboard):
    def __init__(self, text: Text, id: str, items: Any,
                 item_id_getter: Callable = str,
                 on_state_changed: Callable | None = None,
                 when: WhenCondition = None) -> None:
        super().__init__(id, when)
        self._text = text
        self._items = get_items_getter(items)
        self._item_id_getter = item_id_getter
        self._on_state_changed = ensure_event_processor(on_state_changed)

    def _current(self, data: dict, manager: Any) -> tuple[int, list]:
        items = list(self._items(data))
        stored = self.get_widget_data(manager, None)
        ids = [str(self._item_id_getter(i)) for i in items]
        pos = ids.index(stored) if stored in ids else 0
        return pos, items

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        pos, items = self._current(data, manager)
        if not items:
            return []
        scoped = {"data": data, "item": items[pos], "pos": pos + 1, "pos0": pos}
        return [[VKButton(action="callback",
                          label=await self._text.render_text(scoped, manager),
                          callback_data=self.widget_id)]]

    async def _process_own_callback(self, manager: Any) -> bool:
        data = await manager.load_data() if hasattr(manager, "load_data") else {}
        pos, items = self._current(data, manager)
        if items:
            new = items[(pos + 1) % len(items)]
            new_id = str(self._item_id_getter(new))
            self.set_widget_data(manager, new_id)
            await self._on_state_changed.process_event(manager.event, self, manager, new_id)
        return True

    def managed(self, manager: Any):
        return ManagedToggle(self, manager)


class ManagedToggle:
    def __init__(self, widget: Toggle, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def get_checked(self) -> str | None:
        return self._widget.get_widget_data(self._manager, None)


class Checkbox(Keyboard):
    def __init__(self, checked_text: Text, unchecked_text: Text, id: str,
                 default: bool = False, on_state_changed: Callable | None = None,
                 when: WhenCondition = None) -> None:
        super().__init__(id, when)
        self._checked_text = checked_text
        self._unchecked_text = unchecked_text
        self._default = default
        self._on_state_changed = ensure_event_processor(on_state_changed)

    def _is_checked(self, manager: Any) -> bool:
        return bool(self.get_widget_data(manager, self._default))

    async def _render_keyboard(self, data: dict, manager: Any) -> RawKeyboard:
        text = self._checked_text if self._is_checked(manager) else self._unchecked_text
        return [[VKButton(action="callback",
                          label=await text.render_text(data, manager),
                          callback_data=self.widget_id)]]

    async def _process_own_callback(self, manager: Any) -> bool:
        new = not self._is_checked(manager)
        self.set_widget_data(manager, new)
        await self._on_state_changed.process_event(manager.event, self, manager, new)
        return True

    def managed(self, manager: Any):
        return ManagedCheckbox(self, manager)


class ManagedCheckbox:
    def __init__(self, widget: Checkbox, manager: Any) -> None:
        self._widget = widget
        self._manager = manager

    def is_checked(self) -> bool:
        return self._widget._is_checked(self._manager)

    def set_checked(self, value: bool) -> None:
        self._widget.set_widget_data(self._manager, bool(value))
