import pytest

from vkbottle_dialog.api.entities import (
    CarouselElement,
    CarouselSpec,
    KeyboardKind,
    MediaAttachment,
    NewMessage,
    Stack,
    make_stack_key,
)
from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.widgets.kbd.base import VKButton


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


def _carousel(title="t", photo=None, cb="buy"):
    btn = VKButton(action="callback", label="Купить", callback_data=cb)
    return CarouselSpec(
        elements=[CarouselElement(title=title, description="d", photo=photo, buttons=[btn])]
    )


def test_render_hash_includes_carousel():
    base = NewMessage(peer_id=1, text="t", keyboard=None, keyboard_kind=KeyboardKind.NONE)
    with_car = NewMessage(
        peer_id=1, text="t", keyboard=None, keyboard_kind=KeyboardKind.NONE, carousel=_carousel()
    )
    assert base.render_hash() != with_car.render_hash()
    assert (
        with_car.render_hash()
        == NewMessage(
            peer_id=9,
            text="t",
            keyboard=None,
            keyboard_kind=KeyboardKind.NONE,
            carousel=_carousel(),
        ).render_hash()
    )


def test_carousel_descriptor_stable_without_upload():
    # descriptor не трогает photo кроме source_key — не требует аплоуда
    spec = _carousel(photo=MediaAttachment(path="a.png"))
    assert spec.descriptor() == _carousel(photo=MediaAttachment(path="a.png")).descriptor()
    assert spec.descriptor() != _carousel().descriptor()


def test_stack_last_had_carousel_cleared():
    stack = Stack(key=make_stack_key(1, 2, 2))
    stack.last_had_carousel = True
    stack.clear_message()
    assert stack.last_had_carousel is False
