# Changelog

## 0.2.0 — расширение виджетов и медиа

- **`Counter`**: выбор числа (инкремент/декремент) в диапазоне.
- **`Calendar`**: выбор даты; два режима верстки — `COMPACT` (6 дней, пагинация, подходит для бесед)
  и `WIDE` (весь месяц за раз, LS-only), плюс `TimeSelect` для выбора часа/минуты.
- **`List` (постраничный вывод)**: `page_size` для пагинирования текстового списка через `ScrollingGroup`.
- **`ScrollingText`**: прокручиваемый многострочный текст (обёртка над `Text` + `ScrollingGroup`).
- **Медиа-виджеты**: `StaticMedia` + `MediaResolver` для кэширования attachment-строк загруженных медиа.
  Деградация без ошибки при недоступности; требует ручной проверки доступа кросс-peer перед продом.
- **`Text.find`**: поиск виджета по id внутри текстового слота (используется пейджерами для
  `List`/`ScrollingText`).

## 0.1.0 — начальный релиз

Первый релиз `vkbottle-dialog` — порта aiogram-dialog для VK-ботов на vkbottle.

- `Dialog`/`Window`/`DialogManager`: FSM-стейты (`State`, `StatesGroup`), стек интентов, навигация
  (`start`, `switch_to`, `next`, `back`, `done` с передачей результата родителю через
  `on_process_result`), `LaunchMode` (`STANDARD`/`ROOT`/`SINGLE_TOP`/`EXCLUSIVE`), `ShowMode`.
- Текстовые виджеты: `Const`, `Format`, `Case`, `Multi`, `Or`, `List`, `Progress`, условный показ
  через `when=`.
- Клавиатурные виджеты: `Button`, `Url`, навигационные `SwitchTo`/`Back`/`Next`/`Cancel`/`Start`,
  группировка `Group`/`Row`/`Column`, выбор `Select`/`Radio`/`Multiselect`/`Toggle`/`Checkbox`,
  пагинация `ScrollingGroup` + пейджеры (`NumberedPager`, `FirstPage`/`PrevPage`/`CurrentPage`/
  `NextPage`/`LastPage`, `SwitchPage`), синхронизация нескольких скроллов (`sync_scroll`).
- Приём ввода: `MessageInput`, `TextInput` (валидация через `type_factory`, обработка ошибок через
  `on_error`).
- Интеграция с vkbottle: `setup_dialogs()`, правила `InDialog()`/`NotInDialog()` для сосуществования
  с обычными хендлерами, фоновые менеджеры (`bg()`, `BgManagerFactory`) для отправки диалогов вне
  события (крон, вебхуки).
- Хранилища состояния: `MemoryStorage`, `RedisStorage` (`pip install vkbottle-dialog[redis]`).
- Изоляция стеков по (group_id, peer_id, owner_id) — независимые диалоги для участников одной
  беседы.
- Деградация клавиатуры для клиентов без inline-кнопок (`TextKeyboardFactory`, только в личных
  сообщениях) и обработка устаревшего 24-часового окна редактирования сообщений VK (снекбар «Окно
  устарело»).
- 5 самодостаточных примеров в `examples/`: меню, анкета с валидацией, пагинация, вложенные
  диалоги, работа в беседах.

### Известные ограничения

- Один `setup_dialogs()` на процесс (single-instance).
- `StartMode.NEW_STACK` не реализован (`NotImplementedError`).
- Нет `Calendar`, `Counter`, `ListGroup`/`SubManager`, медиа-виджетов, Jinja-шаблонов, карусели,
  `AccessSettings` — см. роадмап в README.
