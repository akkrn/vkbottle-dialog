from __future__ import annotations

import json
from dataclasses import dataclass

from ..api.entities import KeyboardKind
from ..exceptions import DialogConfigError
from ..limits import (
    INLINE_MAX_BUTTONS,
    INLINE_MAX_ROWS,
    LABEL_MAX,
    MAX_PER_ROW,
    TEXT_KB_MAX_BUTTONS,
    TEXT_KB_MAX_ROWS,
)
from ..payload import encode_payload
from .kbd.base import RawKeyboard, VKButton

EMPTY_KEYBOARD_JSON = '{"one_time":false,"inline":false,"buttons":[]}'


@dataclass
class RenderedKeyboard:
    json: str | None
    kind: KeyboardKind


def _label(button: VKButton) -> str:
    label = button.label or " "
    return label[: LABEL_MAX - 1] + "…" if len(label) > LABEL_MAX else label


def _button_doc(button: VKButton, action_type: str, intent_id: str, secret: str | None) -> dict:
    if button.action == "open_link":
        return {"action": {"type": "open_link", "link": button.link, "label": _label(button)}}
    assert button.callback_data is not None
    doc: dict = {
        "action": {
            "type": action_type,
            "label": _label(button),
            "payload": encode_payload(intent_id, button.callback_data, secret),
        }
    }
    if button.color is not None:
        doc["color"] = button.color.value
    return doc


def _validate(raw: RawKeyboard, max_buttons: int, max_rows: int) -> None:
    total = sum(len(row) for row in raw)
    problems = []
    if total > max_buttons:
        problems.append(f"кнопок {total} > {max_buttons}")
    if len(raw) > max_rows:
        problems.append(f"строк {len(raw)} > {max_rows}")
    if any(len(row) > MAX_PER_ROW for row in raw):
        problems.append(f"в строке > {MAX_PER_ROW} кнопок")
    if problems:
        raise DialogConfigError(
            "клавиатура превышает лимиты VK: "
            + ", ".join(problems)
            + " — используйте ScrollingGroup/пагинацию"
        )


class InlineKeyboardFactory:
    def render(self, raw: RawKeyboard, intent_id: str, secret: str | None) -> RenderedKeyboard:
        if not raw:
            return RenderedKeyboard(json=None, kind=KeyboardKind.NONE)
        _validate(raw, INLINE_MAX_BUTTONS, INLINE_MAX_ROWS)
        buttons = [[_button_doc(b, "callback", intent_id, secret) for b in row] for row in raw]
        doc = {"inline": True, "buttons": buttons}
        return RenderedKeyboard(
            json=json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
            kind=KeyboardKind.INLINE,
        )


class TextKeyboardFactory:
    def __init__(self, one_time: bool = False) -> None:
        self._one_time = one_time

    def render(self, raw: RawKeyboard, intent_id: str, secret: str | None) -> RenderedKeyboard:
        if not raw:
            return RenderedKeyboard(json=EMPTY_KEYBOARD_JSON, kind=KeyboardKind.TEXT)
        _validate(raw, TEXT_KB_MAX_BUTTONS, TEXT_KB_MAX_ROWS)
        buttons = [[_button_doc(b, "text", intent_id, secret) for b in row] for row in raw]
        doc = {"one_time": self._one_time, "inline": False, "buttons": buttons}
        return RenderedKeyboard(
            json=json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
            kind=KeyboardKind.TEXT,
        )
