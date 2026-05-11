"""Magic-link authentication.

Two-step flow: POST /auth/login mints a single-use token and emails it;
GET /auth/verify (separate ticket) consumes the token and starts the
session. Tokens are stored as sha256 of their raw bytes — the raw value
exists only inside the email and the verify-step request URL.
"""
