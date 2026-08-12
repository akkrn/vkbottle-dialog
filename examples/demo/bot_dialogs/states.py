"""Все StatesGroup демо-бота: декларируются разом для задач 1-7, чтобы
main.py (задача 1) мог собрать финальное меню инкрементально, а каждая
следующая секция просто дописывала свои окна и диалог в ALL_DIALOGS."""

from vkbottle_dialog.fsm import State, StatesGroup


class Main(StatesGroup):
    MAIN = State()


class Layouts(StatesGroup):
    MAIN = State()
    ROW = State()
    COLUMN = State()
    GROUP = State()


class Scrolls(StatesGroup):
    MAIN = State()
    DEFAULT = State()
    PAGERS = State()
    LIST = State()
    TEXT = State()
    STUB = State()
    SYNC = State()


class Selects(StatesGroup):
    MAIN = State()
    SELECT = State()
    RADIO = State()
    MULTI = State()
    TOGGLE = State()


class CalendarSG(StatesGroup):
    MAIN = State()
    DEFAULT = State()
    CUSTOM = State()
    TIME = State()


class CounterSG(StatesGroup):
    MAIN = State()


class Multiwidget(StatesGroup):
    MAIN = State()


class Switch(StatesGroup):
    MAIN = State()
    INPUT = State()
    LAST = State()


class TextKb(StatesGroup):
    MAIN = State()


class VkFeatures(StatesGroup):
    MAIN = State()
    COLORS = State()
    NESTED = State()


class NameInput(StatesGroup):
    INPUT = State()
