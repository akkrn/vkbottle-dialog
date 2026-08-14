from __future__ import annotations

import hashlib
import secrets
import string
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from ..exceptions import DialogConfigError, DialogStackOverflow
from ..fsm import State
from ..limits import STACK_LIMIT

if TYPE_CHECKING:
    from ..widgets.kbd.base import VKButton

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


def parse_stack_key(key: str) -> tuple[int, int, str, str]:
    _, _, group_id, peer_id, owner_id, stack_id = key.split(":")
    return int(group_id), int(peer_id), owner_id, stack_id


def context_key(intent_id: str) -> str:
    return f"vkd:context:{intent_id}"


@dataclass
class AccessSettings:
    # custom сериализуется storage'ом как есть (см. context/proxy.py
    # _dump_access_settings) — при RedisStorage custom обязан быть
    # JSON-сериализуемым (только dict/list/str/int/float/bool/None), иначе
    # storage.set упадёт на json.dumps.
    user_ids: list[int]
    custom: Any = None


@dataclass
class Context:
    intent_id: str
    stack_key: str
    state: State
    start_data: Any
    dialog_data: dict = field(default_factory=dict)
    widget_data: dict = field(default_factory=dict)
    access_settings: AccessSettings | None = None

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
    last_media_key: str | None = None
    last_kb_hash: str | None = None
    last_had_carousel: bool = False
    access_settings: AccessSettings | None = None

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
        self.last_media_key = None
        self.last_kb_hash = None
        self.last_had_carousel = False


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
class MediaAttachment:
    type: str = "photo"
    path: str | None = None
    url: str | None = None
    attachment: str | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        sources = [s for s in (self.path, self.url, self.attachment) if s]
        if len(sources) != 1:
            raise DialogConfigError("MediaAttachment: ровно одно из path/url/attachment")

    def source_key(self) -> str:
        return f"{self.type}|{self.path or self.url or self.attachment}"


@dataclass
class CarouselElement:
    """Один элемент карусели. photo остаётся НЕразрешённым MediaAttachment —
    MessageManager резолвит его под общим media-пайплайном (кэш/аплоуд), как
    и обычное окно-медиа. buttons/action уже финальны (payload закодирован
    Window.render — там есть intent_id/secret; сам виджет их не видит)."""

    title: str
    description: str
    photo: MediaAttachment | None
    buttons: list[VKButton]
    action: dict[str, str] | None = None


@dataclass
class CarouselSpec:
    elements: list[CarouselElement]

    def descriptor(self) -> str:
        """Стабильный дескриптор для render_hash — без резолва фото (только
        source_key, без аплоуда), детерминированный по уже посчитанным
        title/description/payload/action."""
        parts = []
        for el in self.elements:
            btn_key = "|".join(
                f"{b.label}:{b.action}:{b.callback_data or b.link or ''}" for b in el.buttons
            )
            photo_key = el.photo.source_key() if el.photo else ""
            action_key = (
                "" if el.action is None else f"{el.action.get('type')}:{el.action.get('link', '')}"
            )
            parts.append(
                f"{el.title}\x01{el.description}\x01{photo_key}\x01{btn_key}\x01{action_key}"
            )
        return "\x02".join(parts)


@dataclass
class NewMessage:
    peer_id: int
    text: str
    keyboard: str | None
    keyboard_kind: KeyboardKind
    media: MediaAttachment | None = None
    disable_mentions: bool = True
    dont_parse_links: bool = False
    show_mode: ShowMode = ShowMode.AUTO
    carousel: CarouselSpec | None = None

    def render_hash(
        self, media_override: str | None = None, carousel_override: str | None = None
    ) -> str:
        media_key = (
            media_override
            if media_override is not None
            else (self.media.source_key() if self.media else "")
        )
        carousel_key = (
            carousel_override
            if carousel_override is not None
            else (self.carousel.descriptor() if self.carousel else "")
        )
        raw = f"{self.text}\x00{self.keyboard or ''}\x00{media_key}\x00{carousel_key}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def kb_hash(self) -> str:
        return hashlib.sha256((self.keyboard or "").encode()).hexdigest()[:16]
