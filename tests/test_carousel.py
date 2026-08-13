import json

import pytest

from vkbottle_dialog.api.entities import EventContext
from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.payload import decode_payload
from vkbottle_dialog.widgets.kbd import Button, Carousel
from vkbottle_dialog.widgets.markup import InlineKeyboardFactory, TextKeyboardFactory
from vkbottle_dialog.widgets.media import StaticMedia
from vkbottle_dialog.widgets.text import Const, Format
from vkbottle_dialog.window import Window


class SG(StatesGroup):
    a = State()


def get_id(item):
    return item["id"]


ITEMS = [
    {"id": "1", "name": "Товар 1", "photo": "a.png"},
    {"id": "2", "name": "Товар 2", "photo": "b.png"},
    {"id": "3", "name": "Товар 3", "photo": "c.png"},
]


def make_carousel(items=ITEMS, photo=True, buttons=None, **kw):
    if buttons is None:
        buttons = [Button(Const("Купить"), id="buy")]
    return Carousel(
        id="car",
        items="items",
        item_id_getter=get_id,
        title=Format("{item[name]}"),
        description=Const("описание"),
        buttons=buttons,
        photo=StaticMedia(path=Format("{item[photo]}")) if photo else None,
        **kw,
    )


async def test_render_carousel_builds_spec_with_prefixed_callbacks(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    car = make_carousel()
    spec = await car.render_carousel({"items": ITEMS}, m)

    assert spec is not None
    assert len(spec.elements) == 3
    titles = [e.title for e in spec.elements]
    assert titles == ["Товар 1", "Товар 2", "Товар 3"]
    cds = [btn.callback_data for e in spec.elements for btn in e.buttons]
    assert cds == ["car:1:buy", "car:2:buy", "car:3:buy"]
    assert all(
        e.photo is not None and e.photo.path in ("a.png", "b.png", "c.png") for e in spec.elements
    )


async def test_click_reaches_sub_manager_scoped_handler_for_row(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    clicked = []

    async def on_click(event, widget, manager):
        clicked.append(manager.current_context().widget_data)

    car = make_carousel(buttons=[Button(Const("Купить"), id="buy", on_click=on_click)])
    await car.render_carousel({"items": ITEMS}, m)

    handled = await car.process_callback("car:2:buy", m)

    assert handled is True
    assert len(clicked) == 1
    # SubManager current_context() указывает на строку item_id="2"
    assert m.current_context().widget_data["car"]["2"] == {}


async def test_non_uniform_photo_raises_config_error(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    mixed_items = [
        {"id": "1", "name": "A", "photo": "a.png"},
        {"id": "2", "name": "B", "photo": ""},  # StaticMedia.render_media -> None (пустой path)
    ]
    car = make_carousel(items=mixed_items)
    with pytest.raises(DialogConfigError):
        await car.render_carousel({"items": mixed_items}, m)


async def test_non_uniform_button_count_raises_config_error(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    car = Carousel(
        id="car",
        items="items",
        item_id_getter=get_id,
        title=Format("{item[name]}"),
        description=Const("d"),
        buttons=[
            Button(Const("A"), id="a"),
            Button(
                Const("B"), id="b", when=lambda data, widget, manager: data["item"]["id"] == "2"
            ),
        ],
        photo=None,
    )
    with pytest.raises(DialogConfigError):
        await car.render_carousel({"items": ITEMS}, m)


async def test_more_than_10_items_truncates_with_warning(fake_manager_factory, caplog):
    m = fake_manager_factory(SG.a)
    many_items = [{"id": str(i), "name": f"T{i}", "photo": "a.png"} for i in range(15)]
    car = make_carousel(items=many_items)
    with caplog.at_level("WARNING"):
        spec = await car.render_carousel({"items": many_items}, m)

    assert spec is not None
    assert len(spec.elements) == 10
    assert any("усечено" in rec.message for rec in caplog.records)


async def test_more_than_3_buttons_raises_config_error(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    car = make_carousel(
        buttons=[
            Button(Const("A"), id="a"),
            Button(Const("B"), id="b"),
            Button(Const("C"), id="c"),
            Button(Const("D"), id="d"),
        ]
    )
    with pytest.raises(DialogConfigError):
        await car.render_carousel({"items": ITEMS}, m)


async def test_title_and_description_truncated_to_80(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    long_name = "x" * 90
    items = [{"id": "1", "name": long_name, "photo": "a.png"}]
    car = make_carousel(items=items)
    spec = await car.render_carousel({"items": items}, m)

    assert spec is not None
    title = spec.elements[0].title
    assert len(title) == 80
    assert title.endswith("…")


async def test_render_keyboard_is_always_empty(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    car = make_carousel()
    kb = await car.render_keyboard({"items": ITEMS}, m)
    assert kb == []


async def test_find_recurses_into_child_buttons():
    car = make_carousel()
    assert car.find("car") is car
    found = car.find("buy")
    assert found is not None and found.widget_id == "buy"
    assert car.find("missing") is None


def test_open_link_without_url_raises_config_error():
    with pytest.raises(DialogConfigError):
        Carousel(
            id="car",
            items="items",
            item_id_getter=get_id,
            title=Const("t"),
            description=Const("d"),
            buttons=[],
            element_action="open_link",
        )


def test_open_photo_without_photo_raises_config_error():
    with pytest.raises(DialogConfigError):
        Carousel(
            id="car",
            items="items",
            item_id_getter=get_id,
            title=Const("t"),
            description=Const("d"),
            buttons=[],
            element_action="open_photo",
        )


def ev():
    return EventContext(group_id=1, peer_id=5, owner_id=5, user_id=5, kind="message_new", raw=None)


async def test_window_render_puts_carousel_in_new_message(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    m._data = {"items": ITEMS}
    win = Window(make_carousel(), state=SG.a)

    msg = await win.render(
        m, ev(), m.current_context().intent_id, "s3cr3t", InlineKeyboardFactory()
    )

    assert msg.text == " "  # окно без текста -> обязательный пробел
    assert msg.carousel is not None
    assert len(msg.carousel.elements) == 3
    payload = msg.carousel.elements[1].buttons[0].callback_data
    parsed = decode_payload(payload, "s3cr3t")
    assert parsed is not None
    assert parsed.callback_data == "car:2:buy"
    # render_keyboard остаётся пустым -> обычная inline-клавиатура не шлётся
    assert msg.keyboard is None


async def test_window_forbids_carousel_with_other_kbd_without_text_factory(fake_manager_factory):
    with pytest.raises(DialogConfigError):
        Window(make_carousel(), Button(Const("Далее"), id="next"), state=SG.a)


async def test_window_allows_carousel_with_nav_under_text_factory(fake_manager_factory):
    m = fake_manager_factory(SG.a)
    m._data = {"items": ITEMS}
    win = Window(
        make_carousel(),
        Button(Const("Далее"), id="next"),
        state=SG.a,
        markup_factory=TextKeyboardFactory(button_type="callback"),
    )

    msg = await win.render(m, ev(), m.current_context().intent_id, None, InlineKeyboardFactory())

    assert msg.carousel is not None
    assert msg.keyboard is not None
    doc = json.loads(msg.keyboard)
    assert doc["inline"] is False  # нижняя (TEXT) навигация, не inline


def test_window_forbids_more_than_one_carousel():
    with pytest.raises(DialogConfigError):
        Window(make_carousel(), make_carousel(), state=SG.a)
