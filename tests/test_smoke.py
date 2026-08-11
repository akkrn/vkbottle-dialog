import vkbottle_dialog
from vkbottle_dialog import limits


def test_version():
    assert vkbottle_dialog.__version__ == "0.1.0"


def test_limits():
    assert limits.INLINE_MAX_BUTTONS == 10
    assert limits.EDIT_WINDOW_SECONDS < 86400
