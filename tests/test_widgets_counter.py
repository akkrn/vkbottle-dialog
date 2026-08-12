from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import ButtonColor, Counter


class SG(StatesGroup):
    a = State()


async def test_render_default(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    c = Counter(id="c")
    kb = await c.render_keyboard({}, m)
    row = kb[0]
    assert [b.label for b in row] == ["−", "0", "+"]
    assert [b.callback_data for b in row] == ["c:-", "c:t", "c:+"]
    assert row[0].color is ButtonColor.NEGATIVE
    assert row[2].color is ButtonColor.POSITIVE


async def test_increment_and_bounds(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    changed = []

    async def on_value_changed(event, widget, manager):
        changed.append(widget.get_value())

    c = Counter(id="c", max_value=2, on_value_changed=on_value_changed)
    assert await c.process_callback("c:+", m) is True
    assert await c.process_callback("c:+", m) is True
    assert m.current_context().widget_data["c"] == 2.0
    await c.process_callback("c:+", m)  # граница: тихий no-op
    assert m.current_context().widget_data["c"] == 2.0
    assert changed == [1.0, 2.0]  # no-op не вызвал колбэк


async def test_cycle(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    c = Counter(id="c", min_value=0, max_value=2, cycle=True)
    await c.process_callback("c:-", m)  # 0 → cycle → 2
    assert m.current_context().widget_data["c"] == 2.0


async def test_none_disables_buttons(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    c = Counter(id="c", text=None, minus=None)
    kb = await c.render_keyboard({}, m)
    assert [b.callback_data for b in kb[0]] == ["c:+"]


async def test_text_click_and_managed(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    clicks = []

    async def on_text_click(event, widget, manager):
        clicks.append(widget.get_value())

    c = Counter(id="c", default=5, on_text_click=on_text_click)
    managed = c.managed(m)
    assert managed.get_value() == 5.0
    await c.process_callback("c:t", m)
    assert clicks == [5.0]
    managed.set_value(99)  # клампится в max_value=999999 → 99 ок
    assert managed.get_value() == 99.0
    managed.set_value(-5)
    assert managed.get_value() == 0.0  # min_value
