# vkbottle-dialog

[![CI](https://github.com/akkrn/vkbottle-dialog/actions/workflows/ci.yml/badge.svg)](https://github.com/akkrn/vkbottle-dialog/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/vkbottle-dialog)](https://pypi.org/project/vkbottle-dialog/)
[![Python](https://img.shields.io/pypi/pyversions/vkbottle-dialog)](https://pypi.org/project/vkbottle-dialog/)

Декларативные диалоги для VK-ботов поверх [vkbottle](https://github.com/vkbottle/vkbottle) — порт
[aiogram-dialog](https://github.com/Tishka17/aiogram_dialog) на VK.

## Что это

В обычном vkbottle-боте многошаговые сценарии (анкеты, меню, мастера) собираются вручную: свой FSM,
свои клавиатуры, свои проверки "а что если пользователь написал не то". `vkbottle-dialog` берёт эту
рутину на себя — так же, как `aiogram-dialog` делает это для aiogram/Telegram:

- **Window** — экран (текст + клавиатура + приём ввода), **Dialog** — набор окон на одном FSM-стейте.
- Навигация между окнами (`SwitchTo`, `Back`, `Next`), между диалогами (`Start`, `Cancel`, `done()`
  с результатом родителю).
- Виджеты клавиатур: `Select`/`Radio`/`Multiselect`/`Toggle`/`Checkbox`, группировка `Group`/`Row`/
  `Column`, пагинация `ScrollingGroup`.
- Приём текстового ввода: `TextInput` (с валидацией через `type_factory`), `MessageInput`.
- Хранение состояния диалога: `MemoryStorage` (для разработки) или `RedisStorage` (для прод).

## Quickstart

```python
import os

from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.integration import NotInDialog
from vkbottle_dialog.storage import MemoryStorage
from vkbottle_dialog.widgets.kbd import Cancel, SwitchTo
from vkbottle_dialog.widgets.text import Const


class MenuSG(StatesGroup):
    main = State()
    info = State()


dialog = Dialog(
    Window(
        Const("Главное меню. Выберите пункт:"),
        SwitchTo(Const("О боте"), id="to_info", state=MenuSG.info),
        Cancel(Const("Закрыть")),
        state=MenuSG.main,
    ),
    Window(
        Const("Это демонстрационный бот на vkbottle-dialog."),
        SwitchTo(Const("Назад"), id="to_main", state=MenuSG.main),
        state=MenuSG.info,
    ),
)

bot = Bot(os.environ["VK_TOKEN"])
setup_dialogs(bot, dialog, storage=MemoryStorage())


@bot.on.message(NotInDialog(), text="/start")
async def start(message, dialog_manager):
    await dialog_manager.start(MenuSG.main, mode=StartMode.RESET_STACK)


if __name__ == "__main__":
    bot.run_forever()
```

Больше примеров — в [`examples/`](examples/): `menu.py`, `survey.py` (анкета с валидацией ввода),
`pagination.py` (список на 30 позиций), `nested.py` (вложенные диалоги с возвратом результата),
`chat.py` (работа в беседах).

## Обязательно

**(а) Правило `NotInDialog()` / `InDialog()` для ВСЕХ соседних `@bot.on.message`-хендлеров.**
vkbottle **не блокирует** события между views: `DialogView`, который подключает `setup_dialogs`, —
это всего лишь один из views в `labeler.views()`, он выполняется наравне с остальными хендлерами, а
не "перехватывает" их. Если рядом с диалогом зарегистрирован обычный `@bot.on.message(text="/start")`
без `NotInDialog()`, он сработает поверх активного диалога так, будто диалога нет — сообщение
пользователя внутри диалога может случайно попасть не туда, а повторный `/start` пересоздаст диалог
поверх уже открытого окна. Каждый хендлер, который должен видеть/не видеть активный диалог,
**обязан** использовать `NotInDialog()` (сработает, только если у пользователя нет активного
диалога) или `InDialog()` (сработает, только если диалог активен) — см. `dialog_manager` в
сигнатуре хендлера, который эти правила инжектят.

**(б) В настройках сообщества обязательно включить событие `message_event` и Long Poll API.**
Инлайн-клавиатуры диалогов кликаются через `message_event` (callback-кнопки) — без этого события
нажатия на кнопки будут молча теряться. Long Poll API должен быть включён, версия Long Poll API
5.199 (событие `message_event` доступно с 5.103).

## Соответствие aiogram-dialog → vkbottle-dialog

| aiogram-dialog | vkbottle-dialog | Статус |
|---|---|---|
| `Dialog`, `Window`, `DialogManager` | `Dialog`, `Window`, `DialogManager` | ✅ |
| `Const`, `Format`, `Case`, `Multi`, `Or` | `Const`, `Format`, `Case`, `Multi`, `Or` | ✅ |
| `Button`, `Url`, `SwitchTo`, `Back`, `Next`, `Cancel`, `Start` | то же самое | ✅ |
| `Group`, `Row`, `Column` | `Group`, `Row`, `Column` | ✅ |
| `Select`, `Radio`, `Multiselect`, `Toggle`, `Checkbox` | то же самое | ✅ |
| `ScrollingGroup` + пейджеры (`NumberedPager`, `FirstPage`/`PrevPage`/`CurrentPage`/`NextPage`/`LastPage`, `SwitchPage`) | то же самое | ✅ |
| `MessageInput`, `TextInput` | `MessageInput`, `TextInput` | ✅ |
| `Calendar` | `Calendar` (COMPACT, WIDE) + `TimeSelect` | ✅ |
| `Counter` | `Counter` | ✅ |
| `ListGroup` | `List` (постраничный вывод `page_size`) | ✅ |
| `Text` + `ScrollingGroup` | `ScrollingText` | ✅ |
| Медиа-виджеты (`StaticMedia`) | `StaticMedia` + `MediaResolver` (кэш загрузок) | ✅ |
| `ListGroup`, `SubManager` (v0.3) | `ListGroup` + `SubManager` — per-row состояние, `ManagedListGroup.find_for_item` | ✅ |
| `DynamicMedia` (v0.3) | `DynamicMedia` — селектор `str`/`MagicFilter`/callable | ✅ |
| Карусель (v0.3) | `Carousel` — VK-эксклюзив, за пределами оригинала (template, не media group) | ✅ |
| `StartMode.NEW_STACK` | — | 🗺️ роадмап (пока `NotImplementedError`; без него `AccessSettings.user_ids` в основном не наблюдаем — см. ниже) |
| `AccessSettings` (v0.3) | Хук `access_validator=` в `setup_dialogs` (тихий отказ) — без общих (shared) стеков `user_ids` почти не проявляется, см. «Демо-бот» | ✅ (частично, см. оговорку) |
| Jinja-шаблоны для текста (v0.3) | `Jinja` — extra `[jinja]`, `autoescape=False` (у VK нет HTML) | ✅ |
| Мульти-инстанс (v0.3) | `RedisLockRegistry` — распределённый lock с TTL/heartbeat, `setup_dialogs(locks=...)` | ✅ |

## Календарь и лимиты VK

**`Calendar` (v0.2):** два режима верстки —
- **`CalendarLayout.COMPACT`** (по умолчанию): 6 дней на страницу (по 3 в строке), пагинация; подходит для беседы (≤10 кнопок).
- **`CalendarLayout.WIDE`**: весь месяц за раз (до 35 кнопок), ≤ 5 дней в строке; работает **только в личных сообщениях** (в беседе упадёт с `DialogConfigError`).

**`TimeSelect` (v0.2):** выбор часа/минуты по слотам, постранично, укладывается в лимит 10 кнопок.

**Медиа в диалогах (v0.2):** `StaticMedia` + `MediaResolver` (кэширование attachment-строк за сессию). При отсутствии доступа к медиа вложение деградирует без ошибки; перед продом проверьте доступ кросс-peer (группа ↔ личные сообщения) ручным смоуком.

## Ограничения v0.2

- **Single-instance.** На процесс можно вызвать `setup_dialogs()` один раз — `InDialog()`/
  `NotInDialog()` резолвятся late-binding к последнему активному сетапу.
- **`StartMode.NEW_STACK` не реализован** — `manager.start(..., mode=StartMode.NEW_STACK)` кидает
  `NotImplementedError`. Используйте `StartMode.NORMAL` или `StartMode.RESET_STACK`.
- **`TextKeyboardFactory` работает только в личных сообщениях.** В беседах нижняя (не-инлайн)
  клавиатура общая на весь чат, поэтому рендер диалога с текстовой клавиатурой в беседе — ошибка
  конфигурации (`DialogConfigError`). **То же верно для `CalendarLayout.WIDE`** — в беседе используйте только `COMPACT`.
  Тап по `button_type="text"`-кнопке всегда пересылает окно (это обычное сообщение пользователя,
  `message_new`, а нижняя клавиатура смены не требует); тап по `button_type="callback"`-кнопке при
  неизменной нижней клавиатуре — редактирует окно на месте, без пересылки.
- **24-часовое окно редактирования сообщений VK.** Диалог обновляет своё окно, редактируя одно и то
  же сообщение; когда VK перестаёт разрешать правку (окно устарело), пользователь при клике по
  устаревшей клавиатуре увидит снекбар «Окно устарело, начните заново» вместо тихого зависания
  (настраивается через `stale_snackbar=` в `setup_dialogs`).
- **Лимит инлайн-клавиатуры VK — 10 кнопок** (и до 6 строк, не больше 5 кнопок в строке) — учитывайте
  при проектировании окон с большим числом виджетов; для длинных списков используйте
  `ScrollingGroup`.

## VK-расширения

Помимо API aiogram-dialog, доступны VK-специфичные возможности:

- **`Button(..., color=ButtonColor.POSITIVE)`** — цвет инлайн-кнопки
  (`PRIMARY`/`SECONDARY`/`NEGATIVE`/`POSITIVE`).
- **`Button(..., snackbar="Текст")`** — показать всплывающее уведомление сразу при клике, без ручного
  вызова `manager.answer()`.
- **`manager.answer(snackbar=..., open_link=...)`** — ответ на `message_event` (снекбар и/или
  открытие ссылки на клиенте); доступно только для событий кнопок, не для обычных сообщений.
- **`TextKeyboardFactory(button_type="callback")`** — кнопки нижней (не-инлайн) клавиатуры шлют
  `message_event`, как и инлайн-кнопки, вместо обычного текстового сообщения пользователя: клик не
  засоряет переписку эхом, `manager.answer(snackbar=...)` работает, а неизменную нижнюю клавиатуру
  диалог редактирует на месте вместо пересылки окна (см. «Ограничения» ниже). По умолчанию —
  `button_type="text"` (кнопка постит текст-заглушку как обычное сообщение, обратная совместимость).
  `button_type="callback"` требует клиентской поддержки callback-кнопок (как у инлайн-клавиатуры) —
  на старых клиентах оставьте дефолтный `"text"`; явно заданный `markup_factory` в окне не проходит
  через авто-деградацию по `inline_supported` (см. `manager.py show()`).

## Демо-бот

`examples/demo/` — бот-витрина всех виджетов библиотеки: 12 разделов (Лейауты, Скроллы, Селекты,
Календарь, Счётчик, Мультивиджет, Мастер, Нижняя клавиатура (ЛС), VK-фишки, ListGroup, Карусель (ЛС),
Доступ) из одного главного меню. >10 разделов не влезают в лимит инлайн-клавиатуры (см.
«Ограничения» ниже), поэтому меню — `ScrollingGroup` с пейджером, не плоский список кнопок.
Исходники — `examples/demo/bot_dialogs/`, обход всех окон, подсекций и страниц меню автотестом —
`tests/test_demo_flow.py`.

**Новые в v0.3 разделы:**
- **«📋 ListGroup»** (`bot_dialogs/list_demo.py`) — 3 строки, каждая: `Checkbox` + `Button`
  «удалить» (снекбар), состояние изолировано per-row через `SubManager`. Текст над списком — `Jinja`
  с `{% for %}` по отмеченным строкам, читает их состояние через
  `dialog_manager.find("lg").find_for_item("chk", item_id)`.
- **«🎠 Карусель (ЛС)»** (`bot_dialogs/carousel_demo.py`) — 3-элементная VK-карусель товаров
  (title/description/photo из `examples/demo/media/1..3.png`), callback-кнопка «Выбрать» (снекбар)
  на элемент. Карусель — `template`, а не inline-клавиатура, поэтому окно занимает keyboard-слот
  целиком; нижняя навигация — отдельная callback-клавиатура (`TextKeyboardFactory`). Как и «Нижняя
  клавиатура», секция работает только в ЛС — `TextKeyboardFactory` в беседе поднимает
  `DialogConfigError` (см. «Ограничения»).
- **«🔒 Доступ»** (`bot_dialogs/access_demo.py`) — честная демонстрация кастомного
  `StackAccessValidator` (`AdminOnlyInChatValidator`, подключён в `bot.py` через
  `setup_dialogs(access_validator=...)`): в беседах диалог доступен только администраторам из
  `ADMIN_IDS`. Без `NEW_STACK` (см. таблицу выше) `AccessSettings.user_ids` для дефолтных
  per-owner стеков почти не наблюдаем в демо — раздел и его docstring объясняют, почему выбран
  именно этот сценарий, а не показ `user_ids`.
- **DynamicMedia** — не отдельный раздел, а подсекция «🖼 Динамическое медиа» внутри «✨ VK-фишки»:
  геттер сам выбирает `MediaAttachment` по состоянию диалога (в отличие от `StaticMedia`, где
  путь/url фиксирован в `Text`-виджете).

**Настройка сообщества:**
1. Создайте сообщество VK (или используйте тестовое) и получите ключ доступа сообщества
   (Управление → Работа с API → Ключи доступа).
2. Управление → Работа с API → Long Poll API — включите его, версия Long Poll API **5.199**
   (событие `message_event` доступно с 5.103, но 5.199 — актуальная).
3. Там же, в Типы событий, включите **`message_event`** (и `message_new`) — без него клики по
   инлайн-кнопкам будут молча теряться (см. «Обязательно» выше).

**Получение исходников** (`examples/` не входит в wheel-пакет на PyPI, нужен клон репозитория):

```bash
git clone https://github.com/akkrn/vkbottle-dialog && cd vkbottle-dialog && uv sync
```

(или `pip install -e .` вместо `uv sync`, если вы не используете uv).

**Запуск:**

```bash
VK_TOKEN=<ключ_доступа_сообщества> python -m examples.demo.bot
```

**systemd-юнит** (пример, `/etc/systemd/system/vkd-demo.service`; `/opt/vkbottle-dialog` — клон
репозитория из шага выше, с виртуальным окружением `.venv`, созданным `uv sync`):

```ini
[Unit]
Description=vkbottle-dialog demo bot
[Service]
User=vkbot
WorkingDirectory=/opt/vkbottle-dialog
Environment=VK_TOKEN=<ключ_доступа_сообщества>
ExecStart=/opt/vkbottle-dialog/.venv/bin/python -m examples.demo.bot
Restart=on-failure
[Install]
WantedBy=multi-user.target
```

**Чеклист ручного смоука** (после автотестов — вручную, в реальном клиенте VK):
- [ ] Все 12 секций открываются и рендерятся в личных сообщениях (ЛС), включая пейджер главного
  меню (2-я и 3-я страницы — «ListGroup»/«Карусель»/«Доступ»).
- [ ] **Перед тем как тестировать что-либо в беседе:** добавьте бота в тестовую беседу и впишите
  свой VK user_id в `ADMIN_IDS` (`bot_dialogs/access_demo.py`). `AdminOnlyInChatValidator`
  действует на **весь бот** в беседах, не только на секцию «Доступ» (см. её docstring) — без
  вашего id в списке каждый клик в беседе будет молча проигнорирован (без снекбара, без ошибки в
  клиенте), и следующий пункт чеклиста будет выглядеть как необъяснимый повальный сбой.
- [ ] С вашим id в `ADMIN_IDS` в беседе открываются все секции, **кроме** «Нижней клавиатуры» и
  «🎠 Карусели» — обе ЛС-only (ожидаемо падение с `DialogConfigError`: `TextKeyboardFactory` для
  нижней навигации общая на весь чат, см. «Ограничения v0.2»). Карусель рендерит нижнюю навигацию
  той же `TextKeyboardFactory` (спека §5), поэтому в беседе падает точно так же, как «Нижняя
  клавиатура», а не работает «как в ЛС».
- [ ] В «Скроллы → Заглушка» (`StubScroll`) картинки реально листаются кнопками `‹`/`›`.
- [ ] Медиа, показанное в одном peer (ЛС), корректно переиспользуется (без повторной загрузки и без
  ошибок) при показе того же окна в другом peer (беседе) — кросс-peer кэш `MediaResolver`.
- [ ] С id, которого НЕТ в `ADMIN_IDS`, клики в беседе тихо игнорируются — это проверяет сам
  валидатор (не только его настройку из предыдущих пунктов).

**Живой VK-смоук карусели** (спека §7 — блокирует финальную приёмку `Carousel`; FakeApi-тесты
проверяют только структуру JSON и диспатч, не поведение самого VK):
- [ ] `photo_id` без `access_key` на message-фото реально показывает картинку в карусели (иначе —
  нужна публичная загрузка через wall/album вместо message-аплоада).
- [ ] `messages.edit` с `template` — omit-семантика подтверждена: переход карусель → обычное окно и
  обратно либо явно стирает `template`/`keyboard` явной передачей, либо документированно остаётся
  DELETE_AND_SEND (текущее поведение библиотеки на границе карусель↔клавиатура — безопасный дефолт
  до подтверждения omit-семантики VK).
- [ ] `keyboard` (reply/callback) и `template` в одном сообщении видны оба одновременно — нижняя
  навигация демо (`TextKeyboardFactory`) не перекрывает и не скрывает карусель.
- [ ] Редактирование карусели с изменением числа элементов (например, кликом «Выбрать» подгрузить
  другой набор товаров) корректно перестраивает структуру, а не оставляет старые элементы.

## Установка

```bash
pip install vkbottle-dialog
```

Для хранения состояния диалогов в Redis (прод-режим, вместо `MemoryStorage`):

```bash
pip install vkbottle-dialog[redis]
```

```python
from redis.asyncio import Redis

from vkbottle_dialog.storage import RedisStorage

storage = RedisStorage(Redis.from_url("redis://localhost"))
setup_dialogs(bot, dialog, storage=storage)
```

---

## English

`vkbottle-dialog` is a declarative dialog/window framework for VK bots built on top of
[vkbottle](https://github.com/vkbottle/vkbottle) — a VK port of
[aiogram-dialog](https://github.com/Tishka17/aiogram_dialog). It provides `Dialog`/`Window`
abstractions, navigation widgets, keyboard widgets (`Select`, `Radio`, `Multiselect`, `Toggle`,
`Checkbox`, `ScrollingGroup`), text input handling (`TextInput`, `MessageInput`) and pluggable
storage (`MemoryStorage`, `RedisStorage`).

**Must read before using:** because vkbottle does not block events between views, every neighboring
`@bot.on.message` handler must use the `NotInDialog()` / `InDialog()` rules so it doesn't fire on top
of an active dialog. Your community must also have the `message_event` event and Long Poll API
enabled, or button clicks will be silently dropped.

See the RU section above for the full feature-parity table with aiogram-dialog, v0.1 limitations
(single-instance, no `StartMode.NEW_STACK`, text-keyboard degradation only in DMs, VK's 24h message
edit window, 10-button inline limit) and installation instructions
(`pip install vkbottle-dialog[redis]` for Redis-backed storage). Runnable examples live in
[`examples/`](examples/).

License: Apache-2.0.
