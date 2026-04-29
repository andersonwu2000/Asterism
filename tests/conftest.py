"""Pytest fixtures shared across test modules."""
from __future__ import annotations

import sqlite3
import pytest

from Tooling import db


@pytest.fixture
def conn() -> sqlite3.Connection:
    """In-memory DB with full schema, ready for cascade tests."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    db.init_schema(c)
    yield c
    c.close()
