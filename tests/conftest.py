import pytest
from vkbottle.exception_factory import VKAPIError

from vkbottle_dialog.api.entities import Stack, make_stack_key


class FakeManager:
    def __init__(self, state):
        stack = Stack(key=make_stack_key(1, 2, 2))
        self._ctx = stack.push(state, None)
        self.calls: list[tuple] = []
        self.event = None
        self.show_mode = None
        self._data = {}

    def current_context(self):
        return self._ctx

    async def load_data(self):
        return self._data

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


class FakeApi:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.next_cmid = 100
        self.fail_edit_with: int | None = None
        self.fail_delete_with: int | None = None

    async def request(self, method: str, params: dict) -> dict:
        self.calls.append((method, params))
        if method == "messages.send":
            self.next_cmid += 1
            return {
                "response": [
                    {"peer_id": params["peer_ids"][0], "conversation_message_id": self.next_cmid}
                ]
            }
        if method == "messages.edit":
            if self.fail_edit_with:
                raise VKAPIError[self.fail_edit_with](error_msg="fail")
            return {"response": 1}
        if method == "messages.delete":
            if self.fail_delete_with:
                raise VKAPIError[self.fail_delete_with](error_msg="fail")
            return {"response": 1}
        if method == "messages.sendMessageEventAnswer":
            return {"response": 1}
        return {"response": None}

    def sent(self, method):
        return [p for m, p in self.calls if m == method]


@pytest.fixture
def fake_api():
    return FakeApi()
