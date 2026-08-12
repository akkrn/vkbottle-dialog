# vkbottle-dialog

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
нажатия на кнопки будут молча теряться. Long Poll API должен быть включён и настроен на версию API,
поддерживающую `message_event` (VK API ≥ 5.103).

## Соответствие aiogram-dialog → vkbottle-dialog

| aiogram-dialog | vkbottle-dialog (v0.1) | Статус |
|---|---|---|
| `Dialog`, `Window`, `DialogManager` | `Dialog`, `Window`, `DialogManager` | ✅ |
| `Const`, `Format`, `Case`, `Multi`, `Or` | `Const`, `Format`, `Case`, `Multi`, `Or` | ✅ |
| `Button`, `Url`, `SwitchTo`, `Back`, `Next`, `Cancel`, `Start` | то же самое | ✅ |
| `Group`, `Row`, `Column` | `Group`, `Row`, `Column` | ✅ |
| `Select`, `Radio`, `Multiselect`, `Toggle`, `Checkbox` | то же самое | ✅ |
| `ScrollingGroup` + пейджеры (`NumberedPager`, `FirstPage`/`PrevPage`/`CurrentPage`/`NextPage`/`LastPage`, `SwitchPage`) | то же самое | ✅ |
| `MessageInput`, `TextInput` | `MessageInput`, `TextInput` | ✅ |
| `Calendar` | — | 🗺️ роадмап |
| `Counter` | — | 🗺️ роадмап |
| `ListGroup`, `SubManager` | — | 🗺️ роадмап |
| Медиа-виджеты (`StaticMedia`, `DynamicMedia`) | — | 🗺️ роадмап |
| Jinja-шаблоны для текста | — | 🗺️ роадмап |
| Карусель (media group) | — | 🗺️ роадмап |
| `StartMode.NEW_STACK` | — | 🗺️ роадмап (пока `NotImplementedError`) |
| `AccessSettings` | — | 🗺️ роадмап |
| Мульти-инстанс (несколько `setup_dialogs` в процессе) | — | 🗺️ роадмап (сейчас один `setup_dialogs` на процесс) |

## Ограничения v0.1

- **Single-instance.** На процесс можно вызвать `setup_dialogs()` один раз — `InDialog()`/
  `NotInDialog()` резолвятся late-binding к последнему активному сетапу.
- **`StartMode.NEW_STACK` не реализован** — `manager.start(..., mode=StartMode.NEW_STACK)` кидает
  `NotImplementedError`. Используйте `StartMode.NORMAL` или `StartMode.RESET_STACK`.
- **`TextKeyboardFactory` работает только в личных сообщениях.** В беседах нижняя (не-инлайн)
  клавиатура общая на весь чат, поэтому рендер диалога с текстовой клавиатурой в беседе — ошибка
  конфигурации (`DialogConfigError`).
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
