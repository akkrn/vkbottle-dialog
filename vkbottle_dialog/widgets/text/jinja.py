from __future__ import annotations

from typing import Any

from ...exceptions import DialogConfigError
from ..common import WhenCondition
from .base import Text

# jinja2 — опциональный extra (pip install vkbottle-dialog[jinja]); импорт
# намеренно здесь, а не в общем блоке импортов модуля, чтобы использование
# библиотеки без Jinja-виджета не требовало jinja2.
try:
    import jinja2

    class StubLoader(jinja2.BaseLoader):
        """Заглушка-загрузчик: get_source возвращает саму строку шаблона —
        так текст виджета Jinja и есть шаблон, который env компилирует
        и кеширует."""

        def get_source(self, environment: Any, template: str) -> tuple[str, str, Any]:
            del environment  # unused
            return template, template, lambda: True
except ImportError:  # pragma: no cover - тривиальная ветка без extra
    jinja2 = None  # type: ignore[assignment]
    StubLoader = None  # type: ignore[assignment,misc]

_INSTALL_HINT = "jinja2 не установлен: pip install vkbottle-dialog[jinja]"

_default_env: Any = None


def _require_jinja2() -> Any:
    if jinja2 is None:
        raise DialogConfigError(_INSTALL_HINT)
    return jinja2


def _get_default_env() -> Any:
    global _default_env
    if _default_env is None:
        mod = _require_jinja2()
        _default_env = mod.Environment(
            loader=StubLoader(),
            autoescape=False,  # у VK нет HTML — отличие от оригинала (True)
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _default_env


class Jinja(Text):
    def __init__(self, template_text: str, when: WhenCondition = None) -> None:
        _require_jinja2()
        super().__init__(when)
        self.template_text = template_text

    async def _render_text(self, data: dict, manager: Any) -> str:
        env = getattr(manager, "jinja_env", None) or _get_default_env()
        template = env.get_template(self.template_text)
        if env.is_async:
            return await template.render_async(data)
        return template.render(data)
