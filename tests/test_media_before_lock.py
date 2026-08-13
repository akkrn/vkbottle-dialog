"""Task 3 (v0.3 infra plan): медиа-аплоуд должен происходить ВНЕ stack-lock'а
(спека §6) — иначе долгая загрузка под распределённым Redis-lock'ом (Task 4)
рискует пережить TTL и вызвать split-brain. Инструментированный резолвер
фиксирует, удерживается ли stack-lock в момент апдейта, через полный
DialogView-конвейер (message_new -> start() -> render -> resolve -> send)."""

from vkbottle import Bot

from vkbottle_dialog import Dialog, StartMode, Window, setup_dialogs
from vkbottle_dialog.api.entities import make_stack_key
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.integration.rules import NotInDialog
from vkbottle_dialog.integration.setup import active_setup
from vkbottle_dialog.storage import MemoryStorage
from vkbottle_dialog.widgets.media import StaticMedia
from vkbottle_dialog.widgets.text import Const

GROUP_ID = 99


class SG(StatesGroup):
    menu = State()


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
        "group_id": GROUP_ID,
        "object": {"message": msg, "client_info": msg["client_info"]},
    }


class LockObservingMediaResolver:
    """Подменяет config.media_resolver: вместо реального аплоуда фиксирует,
    удерживается ли stack-lock ИМЕННО в момент вызова resolve()."""

    def __init__(self, locks, stack_key):
        self._locks = locks
        self._stack_key = stack_key
        self.observed_held: list[bool] = []

    async def resolve(self, media, peer_id):
        self.observed_held.append(self._locks.held(self._stack_key))
        return "photo1_1_k"


async def test_media_upload_not_under_stack_lock(fake_api):
    dialog = Dialog(Window(Const("Меню"), StaticMedia(path="a.png"), state=SG.menu))
    bot = Bot("token")
    setup_dialogs(bot, dialog, storage=MemoryStorage(), api=fake_api)

    deps = active_setup()
    stack_key = make_stack_key(GROUP_ID, 5, 5)
    resolver = LockObservingMediaResolver(deps.locks, stack_key)
    deps.config.media_resolver = resolver

    @bot.on.message(NotInDialog(), text="/start")
    async def start(message, dialog_manager):
        await dialog_manager.start(SG.menu, mode=StartMode.RESET_STACK)

    await bot.router.route(raw_message_new("/start"), fake_api)

    assert resolver.observed_held, "resolve() ни разу не вызван — тест ничего не проверил"
    assert all(not held for held in resolver.observed_held), (
        "upload наблюдал stack-lock удержанным — резолв всё ещё внутри критической секции"
    )
    # медиа реально дошло до отправленного сообщения — хоуст не сломал путь
    sent = fake_api.sent("messages.send")[0]
    assert sent["attachment"] == "photo1_1_k"
