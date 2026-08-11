import pytest
from magic_filter import F

from vkbottle_dialog.exceptions import DialogConfigError
from vkbottle_dialog.widgets.text import Case, Const, Format, List, Multi, Or, Progress


async def test_const_format():
    assert await Const("hi").render_text({}, None) == "hi"
    assert await Format("hi {name}").render_text({"name": "Va"}, None) == "hi Va"


async def test_when_hides():
    t = Const("x", when="show")
    assert await t.render_text({"show": False}, None) == ""


async def test_multi_or_operators():
    t = Const("a") + Const("b")
    assert await t.render_text({}, None) == "ab"
    m = Multi(Const("a"), Const("", when="no"), Const("c"), sep="|")
    assert await m.render_text({}, None) == "a|c"
    o = Or(Const("", when="no"), Const("fallback"))
    assert await o.render_text({}, None) == "fallback"


async def test_case():
    c = Case({1: Const("one"), ...: Const("other")}, selector="n")
    assert await c.render_text({"n": 1}, None) == "one"
    assert await c.render_text({"n": 9}, None) == "other"
    cf = Case({True: Const("big"), False: Const("small")}, selector=F["n"] > 5)
    assert await cf.render_text({"n": 10}, None) == "big"


async def test_list_and_progress():
    lst = List(Format("{pos}. {item}"), items="rows")
    assert await lst.render_text({"rows": ["a", "b"]}, None) == "1. a\n2. b"
    p = Progress("done", width=4)
    assert await p.render_text({"done": 50}, None) == "██░░"


async def test_progress_clamping():
    p = Progress("d", width=4)
    assert await p.render_text({"d": 150}, None) == "████"
    assert await p.render_text({"d": -5}, None) == "░░░░"


async def test_case_unhashable_selector():
    c = Case({1: Const("one")}, selector=lambda data, case, mgr: [1, 2])
    with pytest.raises(DialogConfigError, match="нехэшируемое значение"):
        await c.render_text({}, None)
