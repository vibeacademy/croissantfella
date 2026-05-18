"""Taste profile onboarding.

GET /onboard renders a checkbox form populated from the taxonomy enums.
POST /onboard validates submitted values against the same enums and
UPSERTs a ``TasteProfile`` row keyed on ``user_id``. Authentication is
required; anonymous callers get a 302 to ``/auth/login``.
"""
