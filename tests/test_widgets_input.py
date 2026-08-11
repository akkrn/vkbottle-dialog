from types import SimpleNamespace

from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.input import CombinedInput, MessageInput, TextInput


class SG(StatesGroup):
    a = State()


def msg(text="", attachments=()):
    return SimpleNamespace(text=text, attachments=list(attachments))


async def test_text_input_success(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    got = []

    async def on_success(message, widget, manager, value):
        got.append(value)

    ti = TextInput(id="age", type_factory=int, on_success=on_success)
    assert await ti.process_message(msg("42"), m) is True
    assert got == [42]
    assert m.current_context().widget_data["age"] == "42"  # сырой текст
    assert ti.managed(m).get_value() == 42


async def test_text_input_error_path(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    errors = []

    async def on_error(message, widget, manager, error):
        errors.append(str(error))

    ti = TextInput(id="age", type_factory=int, on_error=on_error)
    assert await ti.process_message(msg("не число"), m) is True
    assert len(errors) == 1

    ti_no_handler = TextInput(id="age2", type_factory=int)
    assert await ti_no_handler.process_message(msg("х"), m) is False


async def test_message_input_content_types(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    seen = []

    async def func(message, widget, manager):
        seen.append(message.text)

    mi = MessageInput(func, content_types=["photo"])
    photo = SimpleNamespace(type="photo")
    assert await mi.process_message(msg("p", [photo]), m) is True
    assert await mi.process_message(msg("plain"), m) is False
    assert seen == ["p"]


async def test_combined_first_wins(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    ti = TextInput(id="v", type_factory=int)

    async def fallback(message, widget, manager):
        pass

    combined = CombinedInput(ti, MessageInput(fallback))
    assert await combined.process_message(msg("5"), m) is True
    assert m.current_context().widget_data["v"] == "5"
    assert await combined.process_message(msg("текст"), m) is True  # fallback
