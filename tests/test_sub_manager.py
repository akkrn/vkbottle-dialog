from vkbottle_dialog.api.entities import ShowMode, Stack, StartMode, make_stack_key
from vkbottle_dialog.fsm import State, StatesGroup
from vkbottle_dialog.manager.manager import DialogConfig
from vkbottle_dialog.manager.sub_manager import SubManager
from vkbottle_dialog.widgets.kbd.counter import Counter


class SG(StatesGroup):
    a = State()


class FakeManager:
    """Мимикрирует под ManagerImpl (см. tests/conftest.py::FakeManager),
    расширенный до полной поверхности, которую делегирует SubManager."""

    def __init__(self):
        self._stack = Stack(key=make_stack_key(1, 2, 2))
        self._ctx = self._stack.push(SG.a, start_data="sd")
        self.event = "ev"
        self.middleware_data = {"x": 1}
        self.show_mode = ShowMode.AUTO
        self._config = DialogConfig(jinja_env="JENV")
        self.calls: list[tuple] = []

    def current_context(self):
        return self._ctx

    @property
    def start_data(self):
        return self._ctx.start_data

    @property
    def jinja_env(self):
        return self._config.jinja_env

    @property
    def config(self):
        return self._config

    def has_context(self) -> bool:
        return True

    def current_stack(self):
        return self._stack

    async def load_data(self):
        return {"k": "v"}

    def find(self, widget_id):
        self.calls.append(("find", widget_id))
        return "PARENT_FOUND"

    def find_scroll(self, widget_id):
        return "SCROLL"

    async def show(self):
        self.calls.append(("show",))

    async def answer(self, snackbar=None, open_link=None):
        self.calls.append(("answer", snackbar, open_link))

    async def next(self, show_mode=None):
        self.calls.append(("next", show_mode))

    async def back(self, show_mode=None):
        self.calls.append(("back", show_mode))

    async def done(self, result=None, show_mode=None):
        self.calls.append(("done", result, show_mode))

    async def start(self, state, data=None, mode=None, show_mode=None, access_settings=None):
        self.calls.append(("start", state, data, mode, show_mode, access_settings))

    async def switch_to(self, state, show_mode=None):
        self.calls.append(("switch_to", state, show_mode))

    def bg(self, peer_id=None, user_id=None):
        return ("bg", peer_id, user_id)


def test_row_scoped_widget_data_isolated_between_rows():
    """Один и тот же Counter, отрисованный в двух строках списка (item_id
    "1"/"2"), должен писать данные в РАЗНЫЕ row-словари — состояние строки 1
    не должно быть видно из строки 2."""
    manager = FakeManager()
    counter = Counter(id="cnt")
    sm1 = SubManager(widget=counter, manager=manager, widget_id="cnt", item_id="1")
    sm2 = SubManager(widget=counter, manager=manager, widget_id="cnt", item_id="2")

    counter.set_widget_data(sm1, 5.0)
    counter.set_widget_data(sm2, 9.0)

    assert counter.get_value(sm1) == 5.0
    assert counter.get_value(sm2) == 9.0
    assert manager.current_context().widget_data == {
        "cnt": {"1": {"cnt": 5.0}, "2": {"cnt": 9.0}},
    }


def test_find_returns_row_scoped_managed_widget():
    manager = FakeManager()
    counter = Counter(id="cnt")
    sm = SubManager(widget=counter, manager=manager, widget_id="cnt", item_id="1")

    found = sm.find("cnt")
    assert found is not None
    counter.set_widget_data(sm, 3.0)
    assert found.get_value() == 3.0

    assert sm.find("missing") is None


def test_find_in_parent_delegates_to_parent_manager():
    manager = FakeManager()
    counter = Counter(id="cnt")
    sm = SubManager(widget=counter, manager=manager, widget_id="cnt", item_id="1")

    result = sm.find_in_parent("other")

    assert result == "PARENT_FOUND"
    assert manager.calls == [("find", "other")]


async def test_update_writes_shared_dialog_data_and_shows():
    manager = FakeManager()
    counter = Counter(id="cnt")
    sm = SubManager(widget=counter, manager=manager, widget_id="cnt", item_id="1")

    await sm.update({"a": 1}, show_mode=ShowMode.EDIT)

    assert manager.current_context().dialog_data == {"a": 1}
    assert manager.show_mode == ShowMode.EDIT
    assert manager.calls == [("show",)]


async def test_delegation_smoke():
    manager = FakeManager()
    counter = Counter(id="cnt")
    sm = SubManager(widget=counter, manager=manager, widget_id="cnt", item_id="1")

    assert sm.event == "ev"
    assert sm.middleware_data == {"x": 1}
    assert sm.start_data == "sd"
    assert sm.has_context() is True
    assert sm.current_stack() is manager.current_stack()
    assert await sm.load_data() == {"k": "v"}
    assert sm.jinja_env == "JENV"
    assert sm.config is manager.config
    assert sm.find_scroll("s") == "SCROLL"
    assert sm.bg(peer_id=1) == ("bg", 1, None)

    sm.show_mode = ShowMode.SEND
    assert manager.show_mode == ShowMode.SEND
    assert sm.show_mode == ShowMode.SEND

    await sm.show()
    await sm.answer("snack", "link")
    await sm.next(ShowMode.EDIT)
    await sm.back(ShowMode.EDIT)
    await sm.done("res", ShowMode.EDIT)
    await sm.start(SG.a, data={"d": 1}, mode=StartMode.NORMAL, show_mode=ShowMode.EDIT)
    await sm.switch_to(SG.a, ShowMode.EDIT)

    assert manager.calls == [
        ("show",),
        ("answer", "snack", "link"),
        ("next", ShowMode.EDIT),
        ("back", ShowMode.EDIT),
        ("done", "res", ShowMode.EDIT),
        ("start", SG.a, {"d": 1}, StartMode.NORMAL, ShowMode.EDIT, None),
        ("switch_to", SG.a, ShowMode.EDIT),
    ]
