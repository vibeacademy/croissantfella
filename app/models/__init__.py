"""SQLModel database models.

Concrete models land in #10 (Initialize SQLModel + Alembic with first
migration). This module exists so `alembic/env.py` can import it eagerly
to register `SQLModel.metadata` for autogenerate.
"""
