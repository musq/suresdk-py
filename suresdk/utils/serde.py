import json
from datetime import date, datetime
from enum import Enum
from uuid import UUID


def serialize(obj) -> str:
    """
    This function must always return a "deterministic" string.

    If we use json.dumps(set([2, 3, 1])), then we could get "[2, 1, 3]" or "[1, 3, 2]"
    depending on luck, but if we call serialize(set([2, 3, 1])), then we'll always get
    "[1, 2, 3]".

    We could use this function to calculate hash of an object to determine if it has
    changed since last time.
    """

    return json.dumps(_serialize(obj))


def _serialize(obj):
    if obj is None:
        return None
    if isinstance(obj, (int, float, str, bool)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return str(obj.decode("utf8"))
    if isinstance(obj, (tuple, list)):
        return [serialize(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return [serialize(v) for v in sorted(obj)]
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in sorted(obj.items())}

    return {k: serialize(v) for k, v in sorted(obj.__dict__.items())}
