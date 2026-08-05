import hashlib
import json
from typing import Any


def normalize_hash_text(value: str | None) -> str:
    """
    Aynı metnin gereksiz boşluk farkları nedeniyle farklı hash
    üretmesini engeller.
    """

    return " ".join((value or "").split())


def sha256_text(value: str | None) -> str:
    normalized = normalize_hash_text(value)

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def sha256_json(value: Any) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()
