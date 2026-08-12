from __future__ import annotations

import hashlib
import secrets
import string
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..exceptions import DialogStackOverflow
from ..fsm import State
from ..limits import STACK_LIMIT

_ALPHABET = string.digits + string.ascii_letters
PEER_ID_OFFSET = 2_000_000_000
DEFAULT_STACK_ID = "0"


class ShowMode(Enum):
    AUTO = "auto"
    EDIT = "edit"
    SEND = "send"
    DELETE_AND_SEND = "delete_and_send"
    NO_UPDATE = "no_update"


class StartMode(Enum):
    NORMAL = "normal"
    RESET_STACK = "reset_stack"
    NEW_STACK = "new_stack"


class LaunchMode(Enum):
    STANDARD = "standard"
    ROOT = "root"
    SINGLE_TOP = "single_top"
    EXCLUSIVE = "exclusive"


class KeyboardKind(str, Enum):
    INLINE = "inline"
    TEXT = "text"
    NONE = "none"


def new_intent_id() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(11))


def make_stack_key(
    group_id: int, peer_id: int, owner_id: int, stack_id: str = DEFAULT_STACK_ID
) -> str:
    return f"vkd:stack:{group_id}:{peer_id}:{owner_id}:{stack_id}"


def context_key(intent_id: str) -> str:
    return f"vkd:context:{intent_id}"


@dataclass
class Context:
    intent_id: str
    stack_key: str
    state: State
    start_data: Any
    dialog_data: dict = field(default_factory=dict)
    widget_data: dict = field(default_factory=dict)

    def same(self, other: Context | None) -> bool:
        return (
            other is not None
            and other.intent_id == self.intent_id
            and other.stack_key == self.stack_key
        )


@dataclass
class Stack:
    key: str
    intents: list[str] = field(default_factory=list)
    last_cmid: int | None = None
    last_message_sent_at: float | None = None
    last_keyboard_kind: KeyboardKind = KeyboardKind.NONE
    last_render_hash: str | None = None
    last_text: str | None = None
    inline_supported: bool | None = None

    def push(self, state: State, start_data: Any) -> Context:
        if len(self.intents) >= STACK_LIMIT:
            raise DialogStackOverflow(self.key)
        ctx = Context(
            intent_id=new_intent_id(), stack_key=self.key, state=state, start_data=start_data
        )
        self.intents.append(ctx.intent_id)
        return ctx

    def pop(self) -> str | None:
        return self.intents.pop() if self.intents else None

    def last_intent_id(self) -> str | None:
        return self.intents[-1] if self.intents else None

    def empty(self) -> bool:
        return not self.intents

    def clear_message(self) -> None:
        self.last_cmid = None
        self.last_message_sent_at = None
        self.last_keyboard_kind = KeyboardKind.NONE
        self.last_render_hash = None
        self.last_text = None


@dataclass
class EventContext:
    group_id: int
    peer_id: int
    owner_id: int
    user_id: int
    kind: str
    raw: Any

    @property
    def is_chat(self) -> bool:
        return self.peer_id >= PEER_ID_OFFSET

    @property
    def stack_key(self) -> str:
        return make_stack_key(self.group_id, self.peer_id, self.owner_id)


@dataclass
class NewMessage:
    peer_id: int
    text: str
    keyboard: str | None
    keyboard_kind: KeyboardKind
    attachments: list[str]
    disable_mentions: bool = True
    dont_parse_links: bool = False
    show_mode: ShowMode = ShowMode.AUTO

    def render_hash(self) -> str:
        raw = f"{self.text}\x00{self.keyboard or ''}\x00{','.join(self.attachments)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
