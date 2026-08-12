import pytest

from vkbottle_dialog.api.entities import (
    KeyboardKind,
    MediaAttachment,
    NewMessage,
    Stack,
    make_stack_key,
)
from vkbottle_dialog.exceptions import DialogConfigError


def test_media_attachment_exactly_one_source():
    MediaAttachment(path="a.png")
    MediaAttachment(url="https://e/a.png")
    MediaAttachment(attachment="photo1_2_x")
    with pytest.raises(DialogConfigError):
        MediaAttachment()
    with pytest.raises(DialogConfigError):
        MediaAttachment(path="a.png", url="https://e/a.png")


def test_source_key_stable_and_typed():
    a = MediaAttachment(path="a.png")
    assert a.source_key() == MediaAttachment(path="a.png").source_key()
    assert a.source_key() != MediaAttachment(path="a.png", type="doc").source_key()


def msg(media=None):
    return NewMessage(
        peer_id=1, text="t", keyboard=None, keyboard_kind=KeyboardKind.NONE, media=media
    )


def test_render_hash_includes_media():
    assert msg().render_hash() != msg(MediaAttachment(path="a.png")).render_hash()
    assert (
        msg(MediaAttachment(path="a.png")).render_hash()
        == msg(MediaAttachment(path="a.png")).render_hash()
    )


def test_stack_media_key_cleared():
    stack = Stack(key=make_stack_key(1, 2, 2))
    stack.last_media_key = "photo|a.png"
    stack.clear_message()
    assert stack.last_media_key is None
