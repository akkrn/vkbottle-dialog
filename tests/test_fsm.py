import pytest

from vkbottle_dialog.exceptions import DialogConfigError, UnknownState
from vkbottle_dialog.fsm import State, StatesGroup, StatesRegistry


class SG(StatesGroup):
    first = State()
    second = State()


def test_state_repr_and_group():
    assert SG.first.state == "SG:first"
    assert SG.first.group is SG
    assert SG.first.name == "first"


def test_states_order():
    assert SG.states() == (SG.first, SG.second)


def test_state_equality_and_hash():
    assert SG.first == SG.first
    assert SG.first != SG.second
    assert len({SG.first, SG.first}) == 1


def test_registry_resolve():
    reg = StatesRegistry()
    reg.register(SG)
    assert reg.resolve("SG:second") is SG.second
    with pytest.raises(UnknownState):
        reg.resolve("SG:nope")
    with pytest.raises(UnknownState):
        reg.resolve("Other:first")


def test_registry_register_idempotent_for_same_class():
    reg = StatesRegistry()
    reg.register(SG)
    reg.register(SG)  # тот же класс повторно — не ошибка (несколько окон на группу)
    assert reg.group_of("SG") is SG


def test_registry_rejects_different_class_same_name():
    # M5: имя группы — ключ сериализации состояния (State.state =
    # "Group:name"), совпадение имён у РАЗНЫХ классов сломает resolve()
    # (вернёт не тот класс/состояния) — должно падать раньше, при регистрации.
    class GroupA(StatesGroup):
        x = State()

    class GroupB(StatesGroup):
        y = State()

    GroupB.__name__ = "GroupA"  # форсируем совпадение имени с другим классом

    reg = StatesRegistry()
    reg.register(GroupA)
    with pytest.raises(DialogConfigError):
        reg.register(GroupB)


def test_states_inheritance():
    class Base(StatesGroup):
        a = State()

    class Sub(Base):
        b = State()

    assert Sub.states() == (Base.a, Sub.b)
