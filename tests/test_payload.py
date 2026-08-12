import json

import pytest

from vkbottle_dialog.exceptions import InvalidPayload
from vkbottle_dialog.limits import PAYLOAD_MAX
from vkbottle_dialog.payload import decode_payload, encode_payload


def test_roundtrip_dict_and_str():
    raw = encode_payload("Aa1Bb2Cc3Dd", "menu:5", secret=None)
    assert len(raw) <= 255
    for form in (raw, json.loads(raw)):  # message_new: str, message_event: dict
        parsed = decode_payload(form, secret=None)
        assert parsed.intent_id == "Aa1Bb2Cc3Dd"
        assert parsed.callback_data == "menu:5"


def test_foreign_payloads_return_none():
    assert decode_payload(None, None) is None
    assert decode_payload("not json", None) is None
    assert decode_payload({"command": "start"}, None) is None
    assert decode_payload('{"command":"start"}', None) is None


def test_malformed_vkd_raises():
    with pytest.raises(InvalidPayload):
        decode_payload({"__vkd__": "no-separator"}, None)
    with pytest.raises(InvalidPayload):
        decode_payload({"__vkd__": 42}, None)


def test_hmac_roundtrip_and_spoof():
    raw = encode_payload("Aa1Bb2Cc3Dd", "confirm", secret="s3cret")
    assert decode_payload(raw, secret="s3cret").callback_data == "confirm"
    tampered = json.loads(raw)
    tampered["__vkd__"] = "Aa1Bb2Cc3Dd|delete_all"
    with pytest.raises(InvalidPayload):
        decode_payload(tampered, secret="s3cret")
    with pytest.raises(InvalidPayload):  # подпись отсутствует, но secret включён
        decode_payload({"__vkd__": "Aa1Bb2Cc3Dd|confirm"}, secret="s3cret")


def test_cyrillic_item_not_ascii_escaped():
    raw = encode_payload("Aa1Bb2Cc3Dd", "sel:Москва", secret=None)
    assert "Москва" in raw and "\\u" not in raw


def test_oversize_raises():
    with pytest.raises(InvalidPayload):
        encode_payload("Aa1Bb2Cc3Dd", "w:" + "x" * 300, secret=None)


def test_oversize_str_payload_returns_none_early():
    # M7: чужой/поддельный str-payload может быть сколь угодно длинным (мы
    # сами никогда не шлём больше PAYLOAD_MAX — отсекаем раньше json.loads(),
    # не тратя время на парсинг заведомо мусорной строки.
    huge = "x" * (2 * PAYLOAD_MAX + 1)
    assert decode_payload(huge, None) is None
