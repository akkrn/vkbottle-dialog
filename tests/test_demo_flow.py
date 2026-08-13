"""Task 7: полный обход демо-бота — каждая секция главного меню и каждая
подсекция (Layouts/Scrolls/Selects/Calendar/VkFeatures) реально рендерятся
через FakeApi, что фактически исполняет бюджет клавиатуры §2 для всех окон
демо разом (не только тех, что покрыты юнит-тестами отдельных виджетов)."""

import json

import pytest
from vkbottle import Bot

from examples.demo.bot_dialogs import ALL_DIALOGS
from examples.demo.bot_dialogs.states import Main
from vkbottle_dialog import StartMode, setup_dialogs
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage

# Секции главного меню, чьё стартовое окно — список подсекций (SwitchTo),
# а не самостоятельное окно виджетов. Новую секцию с таким же паттерном
# добавлять сюда — единственный дрифт-guard на полноту этого множества это
# `assert len(section_ids) == 9` ниже (упадёт, если добавили секцию в меню,
# но забыли сюда).
SUBMENU_SECTIONS = {"to_layouts", "to_scrolls", "to_selects", "to_calendar", "to_vk_features"}


def raw_message_new(text, peer=5, from_id=5):
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


def render_count(api) -> int:
    return len(api.sent("messages.send")) + len(api.sent("messages.edit"))


def rendered_keyboard(api) -> dict:
    """Клавиатура последнего отрендеренного окна (send или edit — что позже
    по факту вызова, а не по типу метода)."""
    for method, params in reversed(api.calls):
        if method in ("messages.send", "messages.edit"):
            return json.loads(params["keyboard"])
    raise AssertionError("окно ни разу не отрендерено")


def button_payloads(kb: dict) -> dict[str, dict]:
    """callback_data -> готовый к отправке payload-словарь для каждой
    некликабельной-по-ссылке кнопки клавиатуры (Url пропускается — у неё
    нет payload)."""
    out: dict[str, dict] = {}
    for row in kb["buttons"]:
        for button in row:
            action = button["action"]
            if action["type"] == "open_link":
                continue
            payload = json.loads(action["payload"])
            _, _, callback_data = payload["__vkd__"].partition("|")
            out[callback_data] = payload
    return out


def assert_inline_budget(kb: dict) -> None:
    """Бюджет клавиатуры §2: ≤10 кнопок, ≤6 строк, ≤5 в строке — только для
    инлайн-клавиатур (TextKb рендерит reply-клавиатуру с другими лимитами,
    уже проверенными на этапе рендера в markup.py)."""
    if not kb.get("inline"):
        return
    rows = kb["buttons"]
    assert sum(len(row) for row in rows) <= 10
    assert len(rows) <= 6
    assert all(len(row) <= 5 for row in rows)


@pytest.fixture
def demo_bot(fake_api):
    bot = Bot("token")
    # FakeApi инъецируется параметром api= — media_resolver тоже строится на
    # FakeApi, поэтому StaticMedia (StubScroll в Scrolls) деградирует до
    # окна без вложения вместо реального аплоада (см. media_resolver.py).
    setup_dialogs(bot, *ALL_DIALOGS, storage=MemoryStorage(), api=fake_api)

    @bot.on.message(NotInDialog(), text="/start")
    async def start(message, dialog_manager):
        await dialog_manager.start(Main.MAIN, mode=StartMode.RESET_STACK)

    return bot


async def click(bot, api, payload: dict) -> dict:
    """Кликает payload через message_event и возвращает клавиатуру
    отрендеренного в ответ окна, проверив, что рендер реально произошёл."""
    rc_before = render_count(api)
    await bot.router.route(raw_message_event(payload), api)
    assert render_count(api) > rc_before  # окно отрендерено (send/edit), без исключений
    kb = rendered_keyboard(api)
    assert_inline_budget(kb)
    return kb


async def walk_calendar_zoom(bot, api, days_kb: dict) -> dict:
    """Обходит зум по всем scope календаря DEFAULT (DAYS → MONTHS → страница
    MONTHS через «⋯» → YEARS → MONTHS конкретного года → DAYS конкретного
    месяца), проверяя бюджет клавиатуры на каждом шаге через `click()` —
    регрессия-guard на баг, где MONTHS/YEARS scope превышали лимит в 10
    кнопок и падали с DialogConfigError только при реальном зуме."""
    payloads = button_payloads(days_kb)
    zoom_months_payload = next(p for cd, p in payloads.items() if cd.endswith(":z:months"))
    months_kb = await click(bot, api, zoom_months_payload)

    months_payloads = button_payloads(months_kb)
    more_payload = next(p for cd, p in months_payloads.items() if ":p:" in cd)
    months_kb2 = await click(bot, api, more_payload)

    months_payloads2 = button_payloads(months_kb2)
    years_payload = next(p for cd, p in months_payloads2.items() if cd.endswith(":z:years"))
    years_kb = await click(bot, api, years_payload)

    years_payloads = button_payloads(years_kb)
    year_payload = next(p for cd, p in years_payloads.items() if ":z:months:" in cd)
    year_months_kb = await click(bot, api, year_payload)

    year_months_payloads = button_payloads(year_months_kb)
    month_payload = next(p for cd, p in year_months_payloads.items() if ":z:days:" in cd)
    return await click(bot, api, month_payload)


async def walk_switch_wizard(bot, api, main_kb: dict) -> dict:
    """«Мастер» (`to_switch`) не подменю: его 3 окна (MAIN → INPUT → LAST)
    идут по порядку состояний диалога через `Next()` (виджет с id по
    умолчанию `"__next__"` в обоих окнах — раз он свой в каждом окне, дублей
    id внутри одного окна нет), а не через список SwitchTo, поэтому не
    попадает в SUBMENU_SECTIONS и обходится отдельно."""
    input_kb = await click(bot, api, button_payloads(main_kb)["__next__"])
    last_kb = await click(bot, api, button_payloads(input_kb)["__next__"])
    return button_payloads(last_kb)["__main__"]


async def test_walk_every_demo_section_and_subsection(demo_bot, fake_api):
    bot, api = demo_bot, fake_api

    await bot.router.route(raw_message_new("/start"), api)
    assert render_count(api) == 1  # меню отправлено

    menu_kb = rendered_keyboard(api)
    assert_inline_budget(menu_kb)
    section_ids = list(button_payloads(menu_kb))
    # 9 Start-секций; Url «О библиотеке» без payload — не попадает в словарь
    assert len(section_ids) == 9

    for section_id in section_ids:
        # MAIN_MENU_BUTTON — Start дочернего ROOT-диалога: каждое
        # возвращение в меню пересоздаёт стек с НОВЫМ intent, поэтому
        # payload секции нельзя закэшировать заранее — берём его из
        # последнего фактически отрендеренного меню прямо перед кликом.
        menu_payloads = button_payloads(rendered_keyboard(api))
        section_kb = await click(bot, api, menu_payloads[section_id])

        if section_id in SUBMENU_SECTIONS:
            sub_payloads = button_payloads(section_kb)
            main_menu_payload = sub_payloads.pop("__main__")
            for sub_id, sub_payload in sub_payloads.items():
                # каждый SwitchTo подсекции валиден только пока текущее
                # состояние — MAIN секции (process_callback смотрит окно
                # ТЕКУЩЕГО состояния), поэтому после подсекции возвращаемся
                # «◀ Назад» перед кликом следующей.
                sub_kb = await click(bot, api, sub_payload)
                if section_id == "to_calendar" and sub_id == "to_default":
                    # Calendar DEFAULT — единственная подсекция с зумом
                    # (MONTHS/YEARS scope), где раньше падал бюджет клавиатуры.
                    sub_kb = await walk_calendar_zoom(bot, api, sub_kb)
                back_payload = button_payloads(sub_kb)["__back__"]
                await click(bot, api, back_payload)
        elif section_id == "to_switch":
            main_menu_payload = await walk_switch_wizard(bot, api, section_kb)
        else:
            main_menu_payload = button_payloads(section_kb)["__main__"]

        back_kb = await click(bot, api, main_menu_payload)
        back_payloads = button_payloads(back_kb)
        assert set(back_payloads) == set(menu_payloads)  # снова на главном меню
