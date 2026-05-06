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


@pytest.fixture(autouse=True)
def _disable_reflection_by_default(monkeypatch: pytest.MonkeyPatch):
    """Most tests stub `agent.spawn_llm` and assert the exact number of
    spawn invocations (cold + warm retries + F55 postmortem). The
    Phase-7 reflection spawn (BRIEF/LESSONS feature) would add one more
    spawn per terminal pipeline, breaking those counts. Disable by
    default; tests that specifically exercise reflection re-enable via
    `monkeypatch.delenv` or a localized setenv."""
    monkeypatch.setenv("ASTERISM_LESSONS_REFLECTION_ENABLED", "false")
