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


@pytest.fixture(autouse=True)
def _stub_axiom_probe_by_default(monkeypatch: pytest.MonkeyPatch):
    """Builder / verify_strategy / `_try_promote_sorry_free` run a real
    `lake env lean … #print axioms <name>` probe at promote time. That
    needs a real Lean toolchain + a buildable workspace, which unit
    tests don't provide. Stub at the patched call sites so unit tests
    exercise mark-proved logic without paying the probe overhead.

    Tests that specifically exercise axiom-violation rejection
    (`tests/test_axiom_invariant.py`) override this fixture by
    monkeypatching to a False-returning stub locally."""
    def _stub_ok(*args, **kwargs):
        return True, "axioms ok: [] (test stub)"
    from Tooling.pipeline import _axiom
    from Tooling import verify as _verify_mod
    from Tooling.pipeline import builder as _builder_mod
    from Tooling.pipeline import backward as _backward_mod
    monkeypatch.setattr(_axiom, "axiom_probe_file", _stub_ok)
    monkeypatch.setattr(_axiom, "axiom_probe", _stub_ok)
    # The call sites import via `_axiom.axiom_probe_file`; patching the
    # module-level attribute above suffices for those. `verify.py` uses
    # the symbol via a module-level `from ._axiom import …` so that
    # binding is captured at import — patch it on the verify module too.
    monkeypatch.setattr(_verify_mod, "axiom_probe_file", _stub_ok)
    # Builder + Backward use `_axiom.axiom_probe_file` (via module attr),
    # so the _axiom monkeypatch is enough; explicit re-patches kept off
    # the fast path.
    _ = (_builder_mod, _backward_mod)  # silence unused-import lint
