import json

import pytest

from vkbottle_dialog.api.entities import KeyboardKind
from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.widgets.kbd import ButtonColor, VKButton
from vkbottle_dialog.widgets.markup import (
    EMPTY_KEYBOARD_JSON,
    InlineKeyboardFactory,
    TextKeyboardFactory,
)


def cb(label, data, color=None):
    return VKButton(action="callback", label=label, callback_data=data, color=color)


def test_inline_render():
    raw = [[cb("Да", "yes", ButtonColor.POSITIVE)],
           [VKButton(action="open_link", label="Site", callback_data=None,
                     link="https://e.com")]]
    rendered = InlineKeyboardFactory().render(raw, "IntentIdAb1", None)
    assert rendered.kind is KeyboardKind.INLINE
    doc = json.loads(rendered.json)
    assert doc["inline"] is True
    btn = doc["buttons"][0][0]
    assert btn["action"]["type"] == "callback" and btn["color"] == "positive"
    payload = json.loads(btn["action"]["payload"])
    assert payload["__vkd__"] == "IntentIdAb1|yes"
    link_btn = doc["buttons"][1][0]
    assert link_btn["action"]["type"] == "open_link" and "color" not in link_btn


def test_inline_limits():
    too_many = [[cb(str(i), f"b{i}")] for i in range(11)]
    with pytest.raises(DialogConfigError):
        InlineKeyboardFactory().render(too_many, "IntentIdAb1", None)
    wide = [[cb(str(i), f"b{i}") for i in range(6)]]
    with pytest.raises(DialogConfigError):
        InlineKeyboardFactory().render(wide, "IntentIdAb1", None)


def test_label_truncated():
    raw = [[cb("х" * 60, "b")]]
    doc = json.loads(InlineKeyboardFactory().render(raw, "IntentIdAb1", None).json)
    assert len(doc["buttons"][0][0]["action"]["label"]) == 40


def test_empty_inline_is_none():
    r = InlineKeyboardFactory().render([], "IntentIdAb1", None)
    assert r.json is None and r.kind is KeyboardKind.NONE


def test_text_factory():
    raw = [[cb("Да", "yes")]]
    r = TextKeyboardFactory().render(raw, "IntentIdAb1", None)
    doc = json.loads(r.json)
    assert doc["inline"] is False and r.kind is KeyboardKind.TEXT
    assert doc["buttons"][0][0]["action"]["type"] == "text"
    empty = TextKeyboardFactory().render([], "IntentIdAb1", None)
    assert empty.json == EMPTY_KEYBOARD_JSON
