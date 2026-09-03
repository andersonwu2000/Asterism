"""`Tooling.experiments.push_wake` — one two-turn Strategist push in a
rewound scratch workspace (the 2026-09-03 push experiment, arm B).

The runner writes: it mints a pipeline row, compiles a Context into
`.attempts/`, and spawns the seat against the workspace it is handed.
Pointed at the live workspace it would do all of that inside a running
daemon's state, so the guard is the first thing it does — before the
chdir that would make every workspace look like the current one.
"""
from __future__ import annotations

import io
import sys

import pytest

from Tooling import experiments
from Tooling.experiments import push_wake


def test_push_wake_refuses_a_workspace_a_daemon_owns(tmp_path):
    """A `daemon.pid` beside the DB means the workspace is somebody
    else's; the push must refuse it rather than write into a live run."""
    ws = tmp_path / "live"
    (ws / ".asterism").mkdir(parents=True)
    (ws / "asterism.db").write_text("", encoding="utf-8")
    (ws / ".asterism" / "daemon.pid").write_text("4242 0.0", encoding="utf-8")
    with pytest.raises(SystemExit, match="scratch"):
        push_wake.assert_scratch(ws)


def test_push_wake_accepts_a_scratch_workspace(tmp_path):
    """The negative half: a workspace with no daemon marker passes, so
    the guard above is about the marker and not about refusing always."""
    ws = tmp_path / "scratch"
    (ws / ".asterism").mkdir(parents=True)
    (ws / "asterism.db").write_text("", encoding="utf-8")
    push_wake.assert_scratch(ws)


def test_a_runner_hardens_the_console_before_it_enters_the_pipeline(monkeypatch):
    """These runners are entry points into the same pipeline the CLI
    enters, and the CLI hardens the console first (`_force_utf8_io`).
    They did not: on a cp950 console the `⚠` in a length warning raised
    UnicodeEncodeError INSIDE the wake, and arm C run 2 of the push
    experiment (2026-09-03) died with its proposal written, its
    Adversary round spent and nothing committed."""
    monkeypatch.setattr(
        sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp950"))
    experiments.harden_console()
    print("⚠ i ∉ A")          # the two characters that killed the run
    sys.stdout.flush()
    assert "⚠ i ∉ A" in sys.stdout.buffer.getvalue().decode("utf-8")
