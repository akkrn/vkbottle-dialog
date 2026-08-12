from examples.demo.bot import build_bot


def test_demo_bot_constructs_without_env():
    bot = build_bot("dummy-token")
    assert bot is not None
