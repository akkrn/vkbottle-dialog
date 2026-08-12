import json
from datetime import date

import pytest
from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.api.entities import make_stack_key
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.integration.rules import InDialog, NotInDialog
from vkbottle_dialog.integration.setup import active_setup
from vkbottle_dialog.payload import encode_payload
from vkbottle_dialog.storage import MemoryStorage
from vkbottle_dialog.widgets.input import TextInput
from vkbottle_dialog.widgets.kbd import (
    Button,
    Calendar,
    CalendarConfig,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from vkbottle_dialog.widgets.text import Const, Format


class SG(StatesGroup):
    menu = State()
    form = State()


def raw_message_new(text, peer=5, from_id=5, payload=None):
    msg = {
        "id": 0,
        "conversation_message_id": 10,
        "peer_id": peer,
        "from_id": from_id,
        "text": text,
        "attachments": [],
        "date": 0,
        "version": 0,
        "out": 0,
        "fwd_messages": [],
        "client_info": {
            "inline_keyboard": True,
            "button_actions": [],
            "keyboard": True,
            "lang_id": 0,
        },
    }
    if payload is not None:
        msg["payload"] = payload
    return {
        "type": "message_new",
        "group_id": 99,
        "object": {"message": msg, "client_info": msg["client_info"]},
    }


def raw_message_event(payload: dict, peer=5, user=5, cmid=101):
    return {
        "type": "message_event",
        "group_id": 99,
        "object": {
            "event_id": "ev1",
            "user_id": user,
            "peer_id": peer,
            "conversation_message_id": cmid,
            "payload": payload,
        },
    }


@pytest.fixture
def world(fake_api):
    clicked = []

    async def on_click(event, widget, manager):
        clicked.append("clicked")

    dialog = Dialog(
        Window(
            Const("Меню"),
            Button(Const("Жми"), id="go", on_click=on_click),
            SwitchTo(Const("Форма"), id="tof", state=SG.form),
            state=SG.menu,
        ),
        Window(Const("Введите имя"), TextInput(id="name"), state=SG.form),
    )
    bot = Bot("token")
    # FakeApi инъецируется параметром api= (сетевых вызовов нет);
    # в route FakeApi передаётся как ctx_api.
    bg = setup_dialogs(bot, dialog, storage=MemoryStorage(), api=fake_api)

    @bot.on.message(NotInDialog(), text="/start")
    async def start(message, dialog_manager):
        await dialog_manager.start(SG.menu, mode=StartMode.RESET_STACK)

    return bot, fake_api, clicked, bg


def intent_of(fake_api) -> str:
    kb = json.loads(fake_api.sent("messages.send")[-1]["keyboard"])
    payload = json.loads(kb["buttons"][0][0]["action"]["payload"])
    return payload["__vkd__"].split("|")[0]


async def test_full_flow_start_click_switch_input(world):
    bot, api, clicked, _ = world
    await bot.router.route(raw_message_new("/start"), api)
    assert len(api.sent("messages.send")) == 1  # окно отправлено
    intent = intent_of(api)

    payload = json.loads(encode_payload(intent, "go", None))
    await bot.router.route(raw_message_event(payload), api)
    assert clicked == ["clicked"]
    answers = api.sent("messages.sendMessageEventAnswer")
    assert len(answers) == 1  # ack ровно один

    payload = json.loads(encode_payload(intent, "tof", None))
    await bot.router.route(raw_message_event(payload), api)
    # SwitchTo → рендер формы (edit свежего окна)
    assert api.sent("messages.edit")

    await bot.router.route(raw_message_new("Вася"), api)  # TextInput
    # ввод принят: окно перерисовано send'ом (text-триггер)


async def test_stale_intent_gets_snackbar(world):
    bot, api, _, _ = world
    payload = json.loads(encode_payload("FakeIntent1", "go", None))
    await bot.router.route(raw_message_event(payload), api)
    answers = api.sent("messages.sendMessageEventAnswer")
    assert len(answers) == 1
    assert "snackbar" in answers[0].get("event_data", "")


async def test_foreign_event_ignored(world):
    bot, api, _, _ = world
    await bot.router.route(raw_message_event({"command": "other_lib"}), api)
    assert api.sent("messages.sendMessageEventAnswer") == []  # без ack


async def test_cross_user_replay_rejected_in_chat(world):
    bot, api, clicked, _ = world
    chat_peer = 2_000_000_001
    await bot.router.route(raw_message_new("/start", peer=chat_peer, from_id=7), api)
    intent = intent_of(api)
    # атакующий user=8 реплеит payload владельца user=7 через message_event
    payload = json.loads(encode_payload(intent, "go", None))
    await bot.router.route(raw_message_event(payload, peer=chat_peer, user=8), api)
    # стек-ключ выводится из события → стек атакующего (owner=8) пуст →
    # intent не вершина его стека → отказ + снекбар; on_click НЕ вызван
    assert clicked == []
    answers = api.sent("messages.sendMessageEventAnswer")
    assert len(answers) == 1 and "snackbar" in answers[0].get("event_data", "")
    # владелец (user=7) кликает свой intent — работает
    await bot.router.route(raw_message_event(payload, peer=chat_peer, user=7), api)
    assert clicked == ["clicked"]


async def test_user_handler_not_in_dialog(world):
    bot, api, _, _ = world
    await bot.router.route(raw_message_new("/start"), api)
    intent_before = intent_of(api)
    await bot.router.route(raw_message_new("/start"), api)
    # NotInDialog: диалог активен → пользовательский хендлер /start не сработал,
    # RESET_STACK-пересоздания не было. DialogView перерисовал окно текстовым
    # триггером (send) — допустимо; intent окна остался прежним.
    assert intent_of(api) == intent_before


async def test_indialog_done_clears_stack(world):
    bot, api, _, _ = world

    @bot.on.message(InDialog(), text="/cancel")
    async def cancel(message, dialog_manager):
        await dialog_manager.done()

    await bot.router.route(raw_message_new("/start"), api)
    await bot.router.route(raw_message_new("/cancel"), api)

    deps = active_setup()
    stack = await deps.proxy.load_stack(make_stack_key(99, 5, 5))
    assert stack.empty()


async def test_indialog_switch_to_renders_and_persists(world):
    # Регрессия I1: detached-менеджер, который InDialog() строит для
    # хендлера, раньше не проходил через _run_detached в switch_to/next/
    # back — переключение состояния мутировало throwaway-менеджер без
    # lock/render/commit и терялось бесследно (silent no-op для юзера).
    bot, api, _, _ = world

    @bot.on.message(InDialog(), text="/next")
    async def go_next(message, dialog_manager):
        await dialog_manager.switch_to(SG.form)

    await bot.router.route(raw_message_new("/start"), api)
    sends_before = len(api.sent("messages.send"))
    edits_before = len(api.sent("messages.edit"))

    await bot.router.route(raw_message_new("/next"), api)

    deps = active_setup()
    stack = await deps.proxy.load_stack(make_stack_key(99, 5, 5))
    ctx = await deps.proxy.load_top(stack)
    assert ctx.state is SG.form  # переключение реально закоммичено
    # рендер произошёл (edit свежего окна текстовым триггером)
    assert len(api.sent("messages.send")) + len(api.sent("messages.edit")) > (
        sends_before + edits_before
    )


async def test_message_event_exception_before_dispatch_still_acks(world):
    # M3: до фикса только исключение ВНУТРИ _dispatch гарантировало ack.
    # Исключение раньше (в _validate/load_stack/ManagerImpl(...)) — тоже
    # реальный сценарий (баг, storage-ошибка) — раньше оставляло message_event
    # без ack навсегда (спиннер в клиенте VK висит бесконечно).
    bot, api, _, _ = world
    await bot.router.route(raw_message_new("/start"), api)
    intent = intent_of(api)
    payload = json.loads(encode_payload(intent, "go", None))

    view = bot.labeler.views()["vkd_dialog"]
    orig_validate = view._validate

    async def boom(parsed, stack):
        raise RuntimeError("boom before dispatch")

    view._validate = boom
    try:
        # bot.router.route гасит исключение своим error_handler (логирует),
        # но перед этим handle_event обязан ack'нуть latch.
        await bot.router.route(raw_message_event(payload), api)
    finally:
        view._validate = orig_validate

    answers = api.sent("messages.sendMessageEventAnswer")
    assert len(answers) == 1  # ack ушёл несмотря на исключение до _dispatch


async def test_unknown_state_gets_single_ack_and_recovers(fake_api):
    # Регрессия: персистентный контекст может пережить деплой, в котором
    # состояние переименовали/удалили — _validate()/_load_top_or_recover()
    # обязаны ловить UnknownState (не только UnknownIntent/OutdatedIntent/
    # InvalidPayload), иначе клик остаётся без ack (завис спиннер) и
    # on_unknown_state никогда не вызывается.
    recovered = []

    async def on_unknown_state(event, manager):
        recovered.append(event)

    dialog = Dialog(
        Window(Const("Меню"), Button(Const("Жми"), id="go"), state=SG.menu),
    )
    bot = Bot("token")
    storage = MemoryStorage()
    setup_dialogs(bot, dialog, storage=storage, api=fake_api, on_unknown_state=on_unknown_state)

    @bot.on.message(NotInDialog(), text="/start")
    async def start(message, dialog_manager):
        await dialog_manager.start(SG.menu, mode=StartMode.RESET_STACK)

    await bot.router.route(raw_message_new("/start"), fake_api)
    intent = intent_of(fake_api)

    # Симулируем переименование/удаление состояния после релиза: портим
    # сохранённый контекст так, чтобы его "state" не резолвился.
    raw_ctx = await storage.get(f"vkd:context:{intent}")
    raw_ctx["state"] = "SG:removed_state"
    await storage.set(f"vkd:context:{intent}", raw_ctx)

    payload = json.loads(encode_payload(intent, "go", None))
    await bot.router.route(raw_message_event(payload), fake_api)

    answers = fake_api.sent("messages.sendMessageEventAnswer")
    assert len(answers) == 1  # ack ровно один — без него VK покажет спиннер навечно
    assert "snackbar" in answers[0].get("event_data", "")
    assert len(recovered) == 1  # on_unknown_state вызван


class CatalogSG(StatesGroup):
    items = State()


async def test_pagination_with_window_getter_items_end_to_end(fake_api):
    # Регрессия C1+C2: ManagerImpl.load_data() раньше возвращал только
    # базовые ключи + global-геттер — виджеты вроде ScrollingGroup зовут
    # manager.load_data() на callback-время (посчитать page_count), но
    # window-геттер (items="items") в этот набор не попадал → количество
    # страниц считалось по пустому списку → страница всегда клампилась к 0
    # (клик "›" был silent no-op, спека §5 не соблюдалась).
    async def items_getter(**kwargs):
        return {"items": [{"id": i, "title": f"Item {i}"} for i in range(1, 31)]}

    dialog = Dialog(
        Window(
            Const("Catalog:"),
            ScrollingGroup(
                Select(
                    Format("{item[title]}"),
                    id="select_item",
                    item_id_getter=lambda item: item["id"],
                    items="items",
                ),
                id="sc",
                height=5,
                width=1,
            ),
            state=CatalogSG.items,
            getter=items_getter,
        ),
    )
    bot = Bot("token")
    setup_dialogs(bot, dialog, storage=MemoryStorage(), api=fake_api)

    @bot.on.message(NotInDialog(), text="/catalog")
    async def start(message, dialog_manager):
        await dialog_manager.start(CatalogSG.items, mode=StartMode.RESET_STACK)

    await bot.router.route(raw_message_new("/catalog"), fake_api)
    intent = intent_of(fake_api)

    payload = json.loads(encode_payload(intent, "sc:1", None))
    await bot.router.route(raw_message_event(payload), fake_api)

    deps = active_setup()
    stack = await deps.proxy.load_stack(make_stack_key(99, 5, 5))
    ctx = await deps.proxy.load_top(stack)
    assert ctx.widget_data["sc"] == 1  # страница реально переключилась

    kb = json.loads(fake_api.sent("messages.edit")[-1]["keyboard"])
    first_label = kb["buttons"][0][0]["action"]["label"]
    assert first_label == "Item 6"  # 2-я страница (height=5) начинается с 6-го


class CalendarSG(StatesGroup):
    pick = State()


async def test_calendar_compact_flow_start_shift_month_pick_date(fake_api):
    picked = []

    async def on_click(event, widget, manager, selected):
        picked.append(selected)

    cfg = CalendarConfig(today=lambda: date(2026, 8, 12))
    dialog = Dialog(
        Window(
            Const("Календарь"),
            Calendar(id="cal", config=cfg, on_click=on_click),
            state=CalendarSG.pick,
        ),
    )
    bot = Bot("token")
    setup_dialogs(bot, dialog, storage=MemoryStorage(), api=fake_api)

    @bot.on.message(NotInDialog(), text="/start")
    async def start(message, dialog_manager):
        await dialog_manager.start(CalendarSG.pick, mode=StartMode.RESET_STACK)

    await bot.router.route(raw_message_new("/start"), fake_api)
    assert len(fake_api.sent("messages.send")) == 1  # окно отправлено
    intent = intent_of(fake_api)

    payload = json.loads(encode_payload(intent, "cal:m:+1", None))
    await bot.router.route(raw_message_event(payload), fake_api)
    edited = fake_api.sent("messages.edit")
    assert edited  # edit с новым заголовком месяца
    kb = json.loads(edited[-1]["keyboard"])
    header_label = kb["buttons"][0][1]["action"]["label"]
    assert header_label == "Сентябрь 2026"

    payload = json.loads(encode_payload(intent, "cal:d:2026-09-15", None))
    await bot.router.route(raw_message_event(payload), fake_api)
    assert picked == [date(2026, 9, 15)]  # on_click получил выбранную дату


async def test_dialog_level_getter_reaches_render(fake_api):
    # Регрессия: Dialog(getter=) раньше был мёртвым параметром — Dialog.load_data
    # не имел ни одного вызывающего, так что dialog-level геттер никогда не
    # попадал ни в render, ни в callback-time данные.
    async def dialog_getter(**kwargs):
        return {"greeting": "Привет из dialog-геттера"}

    dialog = Dialog(
        Window(Format("{greeting}"), Button(Const("Ok"), id="ok"), state=SG.menu),
        getter=dialog_getter,
    )
    bot = Bot("token")
    setup_dialogs(bot, dialog, storage=MemoryStorage(), api=fake_api)

    @bot.on.message(NotInDialog(), text="/start")
    async def start(message, dialog_manager):
        await dialog_manager.start(SG.menu, mode=StartMode.RESET_STACK)

    await bot.router.route(raw_message_new("/start"), fake_api)
    text = fake_api.sent("messages.send")[-1]["message"]
    assert text == "Привет из dialog-геттера"
