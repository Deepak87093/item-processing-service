import hashlib
import json


class IdempotencyConflictError(Exception):
    """Same idempotency key used for different request."""


def generate_request_hash(
        item_id: int
) -> str:
    payload = {
        "item_id": item_id,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode('utf-8')
    ).hexdigest()


