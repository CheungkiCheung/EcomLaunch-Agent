"""Application-owned SQLAlchemy metadata for Commerce tables."""

from sqlalchemy.orm import DeclarativeBase


class CommerceBase(DeclarativeBase):
    """Keep Commerce migrations independent from reusable Harness metadata."""
