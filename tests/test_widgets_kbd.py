from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.widgets.kbd import (
    Back,
    Button,
    ButtonColor,
    Cancel,
    Column,
    Group,
    Row,
    SwitchTo,
    Url,
)
from vkbottle_dialog.widgets.text import Const


class SG(StatesGroup):
    a = State()
    b = State()


async def test_button_render_and_click(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    clicks = []

    async def on_click(event, button, manager):
        clicks.append(button.widget_id)

    btn = Button(Const("Оk"), id="ok", on_click=on_click, color=ButtonColor.PRIMARY)
    kb = await btn.render_keyboard({}, m)
    assert kb == [[kb[0][0]]]
    assert kb[0][0].label == "Оk" and kb[0][0].callback_data == "ok"
    assert kb[0][0].color is ButtonColor.PRIMARY

    assert await btn.process_callback("ok", m) is True
    assert clicks == ["ok"]
    assert await btn.process_callback("other", m) is False


async def test_button_snackbar(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    btn = Button(Const("x"), id="x", snackbar="Готово")
    await btn.process_callback("x", m)
    assert ("answer", "Готово") in m.calls


async def test_url_no_callback(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    kb = await Url(Const("Site"), Const("https://e.com")).render_keyboard({}, m)
    assert kb[0][0].action == "open_link" and kb[0][0].callback_data is None


async def test_nav_buttons(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    await SwitchTo(Const("s"), id="sw", state=SG.b).process_callback("sw", m)
    await Back(id="bk").process_callback("bk", m)
    await Cancel(result="r").process_callback("__cancel__", m)
    assert ("switch_to", SG.b) in m.calls
    assert ("back",) in m.calls and ("done", "r") in m.calls


async def test_group_layouts_and_forwarding(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    g = Group(
        Button(Const("1"), id="b1"),
        Button(Const("2"), id="b2"),
        Button(Const("3"), id="b3"),
        width=2,
    )
    kb = await g.render_keyboard({}, m)
    assert [[b.label for b in row] for row in kb] == [["1", "2"], ["3"]]

    row = Row(Button(Const("1"), id="b1"), Button(Const("2"), id="b2"))
    assert len(await row.render_keyboard({}, m)) == 1
    col = Column(Button(Const("1"), id="b1"), Button(Const("2"), id="b2"))
    assert len(await col.render_keyboard({}, m)) == 2

    assert await g.process_callback("b3", m) is True  # форвард ребёнку
    assert await g.process_callback("zzz", m) is False
