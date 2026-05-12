"""In-process rate limiter for magic-link sends.

Fixed hour-bucket counters per key. Suitable for MVP scale (single Cloud
Run instance, ~250 users); for multi-instance scaling, swap for Redis
or a shared store. State is module-global and resets on process restart
— acceptable because magic-link bursts are short-lived and a restart is
worse for the user than a forgotten rate-limit count.

Both limits are enforced inside POST /auth/login. Exceeding either limit
suppresses the Resend call but returns the SAME response shape as a
normal send, preserving email-enumeration safety per
docs/AGENTIC-CONTROLS.md.
"""

import logging
import threading
import time
from dataclasses import dataclass, field

EMAIL_LIMIT_PER_HOUR = 5
IP_LIMIT_PER_HOUR = 20

logger = logging.getLogger(__name__)


@dataclass
class FixedBucketRateLimiter:
    """Atomic check-and-increment with hour buckets."""

    max_per_hour: int
    _counts: dict[tuple[str, int], int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def consume(self, key: str) -> bool:
        """Increment the counter for ``key`` in the current hour bucket
        and return True if the request is allowed (counter was below the
        limit before this call). Atomic against concurrent callers."""
        bucket = int(time.time() // 3600)
        bucket_key = (key, bucket)
        with self._lock:
            current = self._counts.get(bucket_key, 0)
            if current >= self.max_per_hour:
                return False
            self._counts[bucket_key] = current + 1
            return True

    def _reset(self) -> None:
        """Clear all buckets. Test-only — production state is reset by
        process restart."""
        with self._lock:
            self._counts.clear()


email_limiter = FixedBucketRateLimiter(max_per_hour=EMAIL_LIMIT_PER_HOUR)
ip_limiter = FixedBucketRateLimiter(max_per_hour=IP_LIMIT_PER_HOUR)


def check_magic_link_rate_limit(*, email: str, client_ip: str) -> bool:
    """Consume one slot from each limiter. Returns True only if BOTH
    limiters allow the request. Logs at INFO with the suppressed key
    when either limit is hit."""
    email_ok = email_limiter.consume(email.lower())
    ip_ok = ip_limiter.consume(client_ip)
    if not (email_ok and ip_ok):
        logger.info(
            "magic_link_rate_limited",
            extra={
                "email_limit_hit": not email_ok,
                "ip_limit_hit": not ip_ok,
                "client_ip": client_ip,
            },
        )
        return False
    return True
