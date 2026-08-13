"""Секция «Доступ»: демонстрация кастомного StackAccessValidator (спека §4.2).

Честная оговорка (важно понять перед чтением): в v0.3 НЕТ общих (shared)
стеков — NEW_STACK вырезан из дизайна. Каждый диалог живёт в своём
per-owner стеке, и там AccessSettings.user_ids дефолтно равен [owner] —
то есть штатное ограничение по user_ids в этом демо почти не наблюдаемо
(тот, кто мог бы быть ограничен, и так не имеет доступа к чужому стеку —
структурная изоляция уже это гарантирует ДО валидатора). Поэтому здесь
показан другой, реально полезный сценарий кастомного валидатора:
"бот целиком доступен в беседах только администраторам" — AdminOnlyInChat
Validator ниже подключается ОДНИМ параметром access_validator= в
setup_dialogs (см. bot.py) и решает это для КАЖДОГО события в чате,
независимо от того, чей это стек.

Нюанс тайминга (тоже честно, а не спрятан): хук валидатора срабатывает
ПОСЛЕ загрузки стека/контекста, но ДО диспатча callback'а — то есть самое
первое /start в беседе (обычное текстовое сообщение, стек ещё пуст) через
этот хук вообще не проходит и покажет меню кому угодно; проверка включается
только на СЛЕДУЮЩЕМ клике внутри уже существующего стека. Для не-админа
это выглядит так: меню открывается, но любой клик по нему молча
игнорируется (тихий отказ — access_denied_snackbar по умолчанию не задан)."""

from vkbottle_dialog import Dialog, Window
from vkbottle_dialog.widgets.text import Const

from .common import nav_row
from .states import AccessDemo

# Замените на реальные VK user_id администраторов бота.
ADMIN_IDS = {1, 2, 3}


class AdminOnlyInChatValidator:
    """Кастомный StackAccessValidator: в беседах доступ к диалогу есть только
    у ADMIN_IDS, в личных сообщениях (is_chat=False) проверка не действует —
    ограничение по конкретным пользователям в беседе осмысленно только там
    (спека §4.2, ревью-находка про AccessSettings.user_ids без NEW_STACK)."""

    def __init__(self, admin_ids: set[int]) -> None:
        self._admin_ids = admin_ids

    async def is_allowed(self, stack, context, event_ctx) -> bool:
        if not event_ctx.is_chat:
            return True
        return event_ctx.user_id in self._admin_ids


access_demo_dialog = Dialog(
    Window(
        Const("🔒 Доступ: кастомный StackAccessValidator"),
        Const(
            "В личных сообщениях эта секция не отличается от остальных — "
            "проверка вообще не срабатывает (is_chat=False). Смысл "
            "появляется только в беседе, куда бот добавлен как участник: "
            "там setup_dialogs(access_validator=AdminOnlyInChatValidator(...)) "
            "в bot.py разрешает диалог только администраторам из ADMIN_IDS, "
            "а не только «владельцу» своего стека, как это делает "
            "AccessSettings.user_ids по умолчанию (см. docstring этого "
            "модуля — user_ids здесь почти не наблюдаем без NEW_STACK)."
        ),
        nav_row(),
        state=AccessDemo.MAIN,
    ),
)
