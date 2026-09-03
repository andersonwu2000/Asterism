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


def test_result_dump_survives_a_console_codec_the_payload_outruns(monkeypatch):
    """Every experiment runner ends by dumping its result blob to
    stdout, AFTER the run's own artefacts are on disk. On a cp950
    console a payload carrying `∉` (Lean prose does) made that last
    line raise UnicodeEncodeError, so a finished replay reported as a
    crash (arm C run 1, 2026-09-03). The dump must degrade the
    characters, never the run."""
    monkeypatch.setattr(
        sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp950"))
    experiments.print_json({"proof": "i ∉ A"})
    sys.stdout.flush()
    assert b"proof" in sys.stdout.buffer.getvalue()
