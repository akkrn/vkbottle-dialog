"""Task 7/5: полный обход демо-бота — каждая секция главного меню и каждая
подсекция (Layouts/Scrolls/Selects/Calendar/VkFeatures) реально рендерятся
через FakeApi, что фактически исполняет бюджет клавиатуры §2 для всех окон
демо разом (не только тех, что покрыты юнит-тестами отдельных виджетов).

v0.3 (task 5): >10 секций больше не влезают в главное меню как есть (спека
§2), поэтому меню теперь ScrollingGroup — обход ходит через её пейджер, а не
читает все id одним рендером. Плюс новые секции ListGroup/Carousel/Access:
клик по чекбоксу строки ListGroup, клик по callback-кнопке элемента
карусели (payload карусели живёт в template, не в keyboard — отдельный
разбор) и сквозной прогон кастомного access_validator в беседе."""

import json

import pytest
from vkbottle import Bot

from examples.demo.bot_dialogs import ALL_DIALOGS
from examples.demo.bot_dialogs.access_demo import ADMIN_IDS, AdminOnlyInChatValidator
from examples.demo.bot_dialogs.states import Main
from vkbottle_dialog import StartMode, setup_dialogs
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage

# Секции главного меню, чьё стартовое окно — список подсекций (SwitchTo),
# а не самостоятельное окно виджетов. Новую секцию с таким же паттерном
# добавлять сюда — тест обходит её generic-веткой (клик каждой подсекции,
# «◀ Назад», следующая), см. MENU_SECTIONS ниже для дрифт-guard на состав
# самого меню.
SUBMENU_SECTIONS = {"to_layouts", "to_scrolls", "to_selects", "to_calendar", "to_vk_features"}

# Главное меню в порядке кнопок ScrollingGroup(id="menu_sg", height=5,
# width=1) из main.py — 5 секций/страница, странице i соответствует
# индекс // 5. Единственный дрифт-guard на полноту этого списка —
# `assert set(all_ids) == set(MENU_SECTIONS)` ниже (упадёт, если добавили
# секцию в меню, но забыли сюда, или наоборот).
MENU_SECTIONS = [
    "to_layouts",
    "to_scrolls",
    "to_selects",
    "to_calendar",
    "to_counter",
    "to_multiwidget",
    "to_switch",
    "to_text_kb",
    "to_vk_features",
    "to_list",
    "to_carousel",
    "to_access",
]
MENU_SCROLL_ID = "menu_sg"


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
    по факту вызова, а не по типу метода). Правка неизменной нижней (TEXT)
    клавиатуры не передаёт "keyboard" в messages.edit (см. message_manager.py
    §6) — в этом случае клавиатура не изменилась, поэтому берём последнюю
    фактически переданную дальше в истории вызовов."""
    for method, params in reversed(api.calls):
        if method in ("messages.send", "messages.edit") and "keyboard" in params:
            return json.loads(params["keyboard"])
    raise AssertionError("окно ни разу не отрендерено с клавиатурой")


def rendered_template(api) -> dict:
    """template последнего отрендеренного окна с каруселью (спека §5) —
    payload элементов карусели живёт там, а не в "keyboard" (Carousel.
    render_keyboard всегда пуст, см. window.py)."""
    for method, params in reversed(api.calls):
        if method in ("messages.send", "messages.edit") and "template" in params:
            return json.loads(params["template"])
    raise AssertionError("окно ни разу не отрендерено с template (карусель)")


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


def carousel_button_payloads(tpl: dict) -> dict[str, dict]:
    """То же самое, что button_payloads, но для кнопок элементов карусели
    внутри template JSON (структура действия та же — "payload" с тем же
    __vkd__ envelope, encode_payload у Window общий для обоих путей)."""
    out: dict[str, dict] = {}
    for element in tpl["elements"]:
        for button in element.get("buttons", []):
            action = button["action"]
            if action["type"] == "open_link":
                continue
            payload = json.loads(action["payload"])
            _, _, callback_data = payload["__vkd__"].partition("|")
            out[callback_data] = payload
    return out


def real_section_ids(kb: dict) -> list[str]:
    """button_payloads меню без служебных кнопок пейджера ScrollingGroup
    (callback_data вида "menu_sg:{page}") — только настоящие Start-секции."""
    return [k for k in button_payloads(kb) if not k.startswith(f"{MENU_SCROLL_ID}:")]


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
    # FakeApi, поэтому StaticMedia/DynamicMedia/Carousel.photo деградируют
    # до окна без вложения вместо реального аплоада (см. media_resolver.py).
    # access_validator — тот же кастомный, что и в bot.py (секция «Доступ»),
    # чтобы обход демо шёл по реально настроенному боту, а не по дефолту.
    setup_dialogs(
        bot,
        *ALL_DIALOGS,
        storage=MemoryStorage(),
        api=fake_api,
        access_validator=AdminOnlyInChatValidator(ADMIN_IDS),
    )

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


async def goto_menu_page(bot, api, page0_kb: dict, page: int) -> dict:
    """С нулевой страницы меню (page0_kb) один клик по пейджеру ScrollingGroup
    переносит на любую из его страниц: callback_data пейджера — буквально
    "{scroll_id}:{target_page}" (см. ScrollingGroup._pager_row), «›»/«»» на
    3-страничном меню дают её напрямую с page0 без промежуточных кликов."""
    if page == 0:
        return page0_kb
    payloads = button_payloads(page0_kb)
    return await click(bot, api, payloads[f"{MENU_SCROLL_ID}:{page}"])


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


async def walk_text_kb(bot, api, main_kb: dict) -> dict:
    """text_kb использует TextKeyboardFactory(button_type="callback") —
    клик по нижней клавиатуре шлёт message_event, а не обычное сообщение,
    и сама клавиатура при этом не меняется (тот же набор кнопок), поэтому
    AUTO должен отредактировать окно на месте (messages.edit), а не
    удалить+переслать заново — регрессия-guard на баг, где TEXT-клавиатура
    пересылала окно на каждый тап (см. message_manager.py §6)."""
    deletes_before = len(api.sent("messages.delete"))
    edits_before = len(api.sent("messages.edit"))
    kb = await click(bot, api, button_payloads(main_kb)["tk_pizza"])
    assert len(api.sent("messages.delete")) == deletes_before  # без удаления
    assert len(api.sent("messages.edit")) == edits_before + 1  # редактирование на месте
    return kb


async def walk_switch_wizard(bot, api, main_kb: dict) -> dict:
    """«Мастер» (`to_switch`) не подменю: его 3 окна (MAIN → INPUT → LAST)
    идут по порядку состояний диалога через `Next()` (виджет с id по
    умолчанию `"__next__"` в обоих окнах — раз он свой в каждом окне, дублей
    id внутри одного окна нет), а не через список SwitchTo, поэтому не
    попадает в SUBMENU_SECTIONS и обходится отдельно."""
    input_kb = await click(bot, api, button_payloads(main_kb)["__next__"])
    last_kb = await click(bot, api, button_payloads(input_kb)["__next__"])
    return button_payloads(last_kb)["__main__"]


async def walk_list_demo(bot, api, main_kb: dict) -> dict:
    """ListGroup: кликает чекбокс первой строки — callback_data переписан
    ListGroup'ом в "{lg_id}:{item_id}:{child_cb}" (спека §1.2), поэтому
    ищем по префиксу/суффиксу, а не по фиксированному id. Успешный рендер
    без исключений уже проверяет и SubManager-изоляцию строки, и то, что
    Jinja-геттер (dialog_manager.find("lg").find_for_item) не падает."""
    payloads = button_payloads(main_kb)
    chk_payload = next(
        p for cd, p in payloads.items() if cd.startswith("lg:") and cd.endswith(":chk")
    )
    return await click(bot, api, chk_payload)


async def walk_carousel_demo(bot, api) -> dict:
    """Carousel рендерит payload элементов в template, а не в keyboard
    (спека §5) — кликаем callback-кнопку «Выбрать» первого элемента через
    отдельный разбор template, затем возвращаем нижнюю (TEXT) навигацию,
    как обычно, через click()."""
    tpl = rendered_template(api)
    tpl_payloads = carousel_button_payloads(tpl)
    pick_payload = next(p for cd, p in tpl_payloads.items() if cd.endswith(":pick"))
    return await click(bot, api, pick_payload)


async def test_walk_every_demo_section_and_subsection(demo_bot, fake_api):
    bot, api = demo_bot, fake_api

    await bot.router.route(raw_message_new("/start"), api)
    assert render_count(api) == 1  # меню отправлено

    page0_kb = rendered_keyboard(api)
    assert_inline_budget(page0_kb)

    # drift-guard: собираем реальные id со всех 3 страниц меню — если кто-то
    # добавит секцию в main.py, но забудет MENU_SECTIONS (или наоборот),
    # один из двух assert'ов ниже упадёт.
    all_ids: set[str] = set(real_section_ids(page0_kb))
    for page in (1, 2):
        page_kb = await goto_menu_page(bot, api, page0_kb, page)
        assert_inline_budget(page_kb)
        all_ids.update(real_section_ids(page_kb))
    assert len(all_ids) == 12
    assert all_ids == set(MENU_SECTIONS)

    menu_kb = page0_kb
    for i, section_id in enumerate(MENU_SECTIONS):
        page = i // 5
        page_kb = await goto_menu_page(bot, api, menu_kb, page)
        # каждое возвращение в меню — новый ROOT-стек (см. MAIN_MENU_BUTTON,
        # ниже), поэтому payload секции нельзя закэшировать заранее — берём
        # его из последнего фактически отрендеренного меню прямо перед кликом.
        menu_payloads = button_payloads(page_kb)
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
        elif section_id == "to_text_kb":
            section_kb = await walk_text_kb(bot, api, section_kb)
            main_menu_payload = button_payloads(section_kb)["__main__"]
        elif section_id == "to_list":
            section_kb = await walk_list_demo(bot, api, section_kb)
            main_menu_payload = button_payloads(section_kb)["__main__"]
        elif section_id == "to_carousel":
            section_kb = await walk_carousel_demo(bot, api)
            main_menu_payload = button_payloads(section_kb)["__main__"]
        else:
            main_menu_payload = button_payloads(section_kb)["__main__"]

        menu_kb = await click(bot, api, main_menu_payload)
        assert set(real_section_ids(menu_kb)) == set(
            real_section_ids(page0_kb)
        )  # снова на 0-й странице меню


async def test_access_demo_admin_only_in_chat(fake_api):
    """Секция «Доступ»: сквозной прогон AdminOnlyInChatValidator (спека
    §4.2) в беседе — админ кликает как обычно, не-админ получает тихий
    отказ (без рендера, ack без event_data). /start у обоих проходит
    одинаково: хук валидатора применяется только к УЖЕ существующему стеку
    (см. docstring access_demo.py про тайминг) — это тоже часть честной
    демонстрации, а не недосмотр теста."""
    bot = Bot("token")
    setup_dialogs(
        bot,
        *ALL_DIALOGS,
        storage=MemoryStorage(),
        api=fake_api,
        access_validator=AdminOnlyInChatValidator(ADMIN_IDS),
    )

    @bot.on.message(NotInDialog(), text="/start")
    async def start(message, dialog_manager):
        await dialog_manager.start(Main.MAIN, mode=StartMode.RESET_STACK)

    chat_peer = 2_000_000_001
    admin_id = next(iter(ADMIN_IDS))
    non_admin_id = max(ADMIN_IDS) + 1000
    assert non_admin_id not in ADMIN_IDS

    # админ: /start + клик обрабатываются как обычно
    await bot.router.route(raw_message_new("/start", peer=chat_peer, from_id=admin_id), fake_api)
    admin_menu_kb = rendered_keyboard(fake_api)
    admin_payload = next(iter(button_payloads(admin_menu_kb).values()))
    rc_before = render_count(fake_api)
    await bot.router.route(
        raw_message_event(admin_payload, peer=chat_peer, user=admin_id), fake_api
    )
    assert render_count(fake_api) > rc_before

    # не-админ: свой собственный стек в том же чате (owner = from_id для
    # бесед) — /start показывает меню как обычно (стек ещё пуст, хук не
    # применяется), но клик по нему тихо отклоняется.
    await bot.router.route(
        raw_message_new("/start", peer=chat_peer, from_id=non_admin_id), fake_api
    )
    non_admin_menu_kb = rendered_keyboard(fake_api)
    non_admin_payload = next(iter(button_payloads(non_admin_menu_kb).values()))
    rc_before = render_count(fake_api)
    answers_before = len(fake_api.sent("messages.sendMessageEventAnswer"))
    await bot.router.route(
        raw_message_event(non_admin_payload, peer=chat_peer, user=non_admin_id), fake_api
    )
    assert render_count(fake_api) == rc_before  # тихий отказ — без рендера
    answers = fake_api.sent("messages.sendMessageEventAnswer")
    assert len(answers) == answers_before + 1
    assert "event_data" not in answers[-1]
