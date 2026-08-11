"""Simple in-memory anti-flood check. Fine for the target scale (~100 users);
no need for Redis or persistence -- a restart just resets everyone's cooldown.
"""

import time

_last_message_at: dict[int, float] = {}


def allow(user_id: int, rate_limit_seconds: float) -> bool:
    now = time.monotonic()
    last = _last_message_at.get(user_id)
    if last is not None and (now - last) < rate_limit_seconds:
        return False
    _last_message_at[user_id] = now
    return True
