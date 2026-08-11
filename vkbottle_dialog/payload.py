from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

from .exceptions import InvalidPayload
from .limits import PAYLOAD_MAX

VKD_KEY = "__vkd__"
SIG_KEY = "s"
SEP = "|"


@dataclass
class ParsedPayload:
    intent_id: str
    callback_data: str


def _sign(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), value.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest)[:16].decode()


def encode_payload(intent_id: str, callback_data: str, secret: str | None) -> str:
    value = f"{intent_id}{SEP}{callback_data}"
    doc: dict[str, str] = {VKD_KEY: value}
    if secret is not None:
        doc[SIG_KEY] = _sign(value, secret)
    raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if len(raw) > PAYLOAD_MAX:
        raise InvalidPayload(
            f"payload {len(raw)} > {PAYLOAD_MAX} символов — сократите widget id/item"
        )
    return raw


def decode_payload(raw: dict | str | None, secret: str | None) -> ParsedPayload | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
    if not isinstance(raw, dict) or VKD_KEY not in raw:
        return None
    value = raw[VKD_KEY]
    if not isinstance(value, str) or SEP not in value:
        raise InvalidPayload("битый формат __vkd__")
    if secret is not None:
        sig = raw.get(SIG_KEY)
        if not isinstance(sig, str) or not hmac.compare_digest(sig, _sign(value, secret)):
            raise InvalidPayload("подпись payload не сошлась")
    intent_id, _, callback_data = value.partition(SEP)
    if not intent_id or not callback_data:
        raise InvalidPayload("пустой intent или callback_data")
    return ParsedPayload(intent_id=intent_id, callback_data=callback_data)
