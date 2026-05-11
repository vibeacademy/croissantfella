"""Token generation and hashing for magic-link sign-in.

The raw token is 32 bytes of `secrets.token_bytes` rendered as URL-safe
base64 (no padding). Only the sha256 digest of the raw bytes is stored;
the raw value lives in the email body and the verify-step request URL.
"""

import base64
import hashlib
import secrets

TOKEN_NBYTES = 32


def generate_token() -> str:
    """Return a URL-safe base64-encoded random token (no padding)."""
    raw_bytes = secrets.token_bytes(TOKEN_NBYTES)
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")


def hash_token(raw_token: str) -> bytes:
    """Return the sha256 digest of the raw token, as 32 raw bytes."""
    return hashlib.sha256(raw_token.encode("ascii")).digest()
