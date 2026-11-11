from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware ``datetime``."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Global declarative base shared by every ORM model in the project.

    Importing this single ``Base`` keeps all models in one SQLAlchemy
    registry, which is required for cross-file ``relationship()`` links and
    for ``Base.metadata.create_all()`` to see every table.
    """


__all__ = ["Base", "utcnow"]
