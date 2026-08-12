import pytest

from vkbottle_dialog.api.entities import EventContext
from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.markup import InlineKeyboardFactory
from vkbottle_dialog.widgets.media import StaticMedia
from vkbottle_dialog.widgets.text import Const, Format
from vkbottle_dialog.window import Window


class SG(StatesGroup):
    a = State()


async def test_static_media_renders_formatted_path(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    sm = StaticMedia(path=Format("media/{n}.png"))
    media = await sm.render_media({"n": 3}, m)
    assert media.path == "media/3.png" and media.type == "photo"


async def test_when_hides(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    sm = StaticMedia(path="a.png", when="show")
    assert await sm.render_media({"show": False}, m) is None


def test_two_media_widgets_rejected():
    with pytest.raises(DialogConfigError):
        Window(Const("t"), StaticMedia(path="a.png"), StaticMedia(path="b.png"), state=SG.a)


def test_ambiguous_static_media_rejected():
    with pytest.raises(DialogConfigError):
        StaticMedia(path="a.png", url="http://example.com")


async def test_window_render_carries_media(fake_manager_factory):
    from vkbottle_dialog.api.entities import Stack, make_stack_key

    class RenderManager:
        def __init__(self, ctx):
            self._ctx = ctx
            self.event = None

        def current_context(self):
            return self._ctx

        async def load_data(self):
            return {}

    stack = Stack(key=make_stack_key(1, 5, 5))
    ctx = stack.push(SG.a, None)
    win = Window(Const("t"), StaticMedia(path="a.png"), state=SG.a)
    ev = EventContext(group_id=1, peer_id=5, owner_id=5, user_id=5, kind="message_new", raw=None)
    msg = await win.render(RenderManager(ctx), ev, ctx.intent_id, None, InlineKeyboardFactory())
    assert msg.media is not None and msg.media.path == "a.png"
