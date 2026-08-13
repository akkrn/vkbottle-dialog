from __future__ import annotations

from ..api.entities import Context, EventContext, Stack


class DefaultAccessValidator:
    """Дефолтный StackAccessValidator (спека §4.2).

    Эффективные settings — контекста, ЕСЛИ контекст загружен (даже когда
    его поле None → доступ ОТКРЫТ, легаси-совместимость со старыми
    записями до этой фичи), иначе — стека."""

    async def is_allowed(
        self, stack: Stack, context: Context | None, event_ctx: EventContext
    ) -> bool:
        if not event_ctx.is_chat:
            return True
        settings = context.access_settings if context is not None else stack.access_settings
        if settings is None:
            return True
        if not settings.user_ids:
            return True
        return event_ctx.user_id in settings.user_ids


__all__ = ["DefaultAccessValidator"]
