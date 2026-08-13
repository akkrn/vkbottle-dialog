import pytest

from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.manager.sub_manager import SubManager
from vkbottle_dialog.widgets.text import jinja as jinja_module
from vkbottle_dialog.widgets.text.jinja import Jinja


class FakeManager:
    def __init__(self, jinja_env=None):
        self.jinja_env = jinja_env


async def test_for_loop_render():
    widget = Jinja("{% for x in xs %}{{ x }} {% endfor %}")
    result = await widget.render_text({"xs": [1, 2, 3]}, None)
    assert result == "1 2 3 "


async def test_custom_env_is_used_for_render():
    import jinja2

    def shout(value):
        return f"{value}!!!"

    env = jinja2.Environment(
        loader=jinja_module.StubLoader(),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["shout"] = shout

    manager = FakeManager(jinja_env=env)
    widget = Jinja("{{ name|shout }}")

    assert await widget.render_text({"name": "hi"}, manager) == "hi!!!"


async def test_async_env_renders_via_render_async():
    import jinja2

    env = jinja2.Environment(
        loader=jinja_module.StubLoader(),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        enable_async=True,
    )
    manager = FakeManager(jinja_env=env)
    widget = Jinja("hello {{ name }}")

    assert await widget.render_text({"name": "world"}, manager) == "hello world"


async def test_jinja_inside_list_group_row_via_sub_manager():
    class DummyWidget:
        def find(self, widget_id):
            return None

    manager = FakeManager(jinja_env=None)
    sub_manager = SubManager(widget=DummyWidget(), manager=manager, widget_id="w", item_id="1")
    widget = Jinja("row {{ n }}")

    assert await widget.render_text({"n": 1}, sub_manager) == "row 1"


def test_missing_jinja2_raises_clear_error(monkeypatch):
    monkeypatch.setattr(jinja_module, "jinja2", None)
    with pytest.raises(DialogConfigError, match=r"pip install vkbottle-dialog\[jinja\]"):
        Jinja("x")
