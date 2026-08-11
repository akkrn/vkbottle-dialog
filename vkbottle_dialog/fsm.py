from __future__ import annotations

from .exceptions import UnknownState


class State:
    def __init__(self) -> None:
        self._name: str | None = None
        self._group: type[StatesGroup] | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name
        self._group = owner

    @property
    def name(self) -> str:
        assert self._name is not None, "State не привязан к StatesGroup"
        return self._name

    @property
    def group(self) -> type[StatesGroup]:
        assert self._group is not None, "State не привязан к StatesGroup"
        return self._group

    @property
    def state(self) -> str:
        return f"{self.group.__name__}:{self.name}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, State) and other.state == self.state

    def __hash__(self) -> int:
        return hash(self.state)

    def __repr__(self) -> str:
        return f"<State {self.state}>"


class StatesGroup:
    @classmethod
    def states(cls) -> tuple[State, ...]:
        return tuple(v for v in vars(cls).values() if isinstance(v, State))

    @classmethod
    def __group_name__(cls) -> str:
        return cls.__name__


class StatesRegistry:
    def __init__(self) -> None:
        self._groups: dict[str, type[StatesGroup]] = {}

    def register(self, group: type[StatesGroup]) -> None:
        self._groups[group.__name__] = group

    def group_of(self, name: str) -> type[StatesGroup]:
        try:
            return self._groups[name]
        except KeyError:
            raise UnknownState(f"неизвестная группа состояний: {name}") from None

    def resolve(self, raw: str) -> State:
        group_name, _, state_name = raw.partition(":")
        group = self.group_of(group_name)
        for st in group.states():
            if st.name == state_name:
                return st
        raise UnknownState(f"нет состояния {raw}")
