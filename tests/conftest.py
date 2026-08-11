import pytest

from vkbottle_dialog.api.entities import Stack, make_stack_key


class FakeManager:
    def __init__(self, state):
        stack = Stack(key=make_stack_key(1, 2, 2))
        self._ctx = stack.push(state, None)
        self.calls: list[tuple] = []
        self.event = None
        self.show_mode = None

    def current_context(self):
        return self._ctx

    async def switch_to(self, state, show_mode=None):
        self.calls.append(("switch_to", state))

    async def next(self, show_mode=None):
        self.calls.append(("next",))

    async def back(self, show_mode=None):
        self.calls.append(("back",))

    async def done(self, result=None, show_mode=None):
        self.calls.append(("done", result))

    async def start(self, state, data=None, mode=None, show_mode=None):
        self.calls.append(("start", state, data))

    async def answer(self, snackbar=None, open_link=None):
        self.calls.append(("answer", snackbar))


@pytest.fixture
def fake_manager_factory():
    return FakeManager
