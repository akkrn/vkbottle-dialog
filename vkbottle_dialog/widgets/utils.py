from __future__ import annotations

from typing import Any

from ..exceptions import DialogConfigError
from .input import BaseInput, CombinedInput
from .kbd.base import Keyboard
from .kbd.group import Group
from .text.base import Const, Multi, Text


def ensure_widgets(widgets: tuple[Any, ...]) -> tuple[Text, Keyboard, BaseInput | None]:
    texts: list[Text] = []
    keyboards: list[Keyboard] = []
    inputs: list[BaseInput] = []
    for widget in widgets:
        if isinstance(widget, str):
            texts.append(Const(widget))
        elif isinstance(widget, Text):
            texts.append(widget)
        elif isinstance(widget, Keyboard):
            keyboards.append(widget)
        elif isinstance(widget, BaseInput):
            inputs.append(widget)
        else:
            raise DialogConfigError(f"неизвестный виджет: {widget!r}")
    text = texts[0] if len(texts) == 1 else Multi(*texts, sep="\n")
    keyboard = keyboards[0] if len(keyboards) == 1 else Group(*keyboards)
    input_: BaseInput | None
    if not inputs:
        input_ = None
    elif len(inputs) == 1:
        input_ = inputs[0]
    else:
        input_ = CombinedInput(*inputs)
    return text, keyboard, input_
