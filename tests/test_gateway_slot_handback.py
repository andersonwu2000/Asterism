"""The gateway slot a dead spawn still holds must be handed back
BEFORE the directory holding its token is deleted (2026-08-13).

The gateway outlives daemons on purpose, so a daemon that starts into
an existing gateway inherits whatever its predecessor left claimed.
`_gateway_session.token` — the only handle that can release such a
claim — lives inside `.attempts/<pipeline_id>/`, which is exactly what
recovery's orphan sweep deletes. Deleting first destroyed the evidence
twice over: no token to release, and no sandbox manifest either, so the
gateway's own liveness probe read "owner unknown → assume alive" and
held 3 of 4 slots to the 3600s ceiling. Every /register from the new
daemon answered "no free worker slot"; it exited in ~780s.

Ordering is the whole invariant, so that is what these pin: the release
must observe a directory that still exists.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import recovery


def _dead_spawn_dir(workspace: Path, pipeline_id: str, *,
                    token: "str | None") -> Path:
    """An orphan attempts dir as a hard-killed daemon leaves one: a
    sandbox manifest naming a pid that cannot be running, and (unless
    `token` is None) the gateway session token that spawn registered."""
    d = workspace / ".attempts" / pipeline_id
    (d / "sandbox").mkdir(parents=True)
    (d / "sandbox" / "_manifest.json").write_text(
        json.dumps({"owner_pid": 2 ** 31 - 1}), encoding="utf-8")
    if token is not None:
        (d / "_gateway_session.token").write_text(token, encoding="utf-8")
    return d


def test_the_slot_is_handed_back_before_the_dir_is_deleted(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordering, stated as the release can still see its own dir."""
    seen: list[tuple[str, bool]] = []

    def _fake_release(attempts_dir: Path) -> bool:
        tok = attempts_dir / "_gateway_session.token"
        # The assertion that matters: we are called while the handle is
        # still on disk. A release moved after the rmtree sees nothing.
        seen.append((attempts_dir.name, tok.exists()))
        return tok.exists()

    import Tooling.pipeline as _pipeline
    monkeypatch.setattr(_pipeline, "_release_session", _fake_release)

    d = _dead_spawn_dir(tmp_path, "pipe-dead", token="tok-abc")
    recovery.recover_at_startup(conn, workspace=tmp_path)

    assert seen == [("pipe-dead", True)], (
        "recovery must release the gateway session while the token file "
        f"still exists; got {seen}")
    assert not d.exists(), "the orphan dir should still be swept afterwards"


def test_a_live_spawns_slot_is_never_touched(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#90's sparing rule wins first: a live owner's dir is skipped, so
    its slot must not be released out from under it. Handing back a
    working spawn's slot would be worse than the leak."""
    import os

    calls: list[str] = []
    import Tooling.pipeline as _pipeline
    monkeypatch.setattr(_pipeline, "_release_session",
                        lambda d: calls.append(d.name) or True)

    d = tmp_path / ".attempts" / "pipe-live"
    (d / "sandbox").mkdir(parents=True)
    (d / "sandbox" / "_manifest.json").write_text(
        json.dumps({"owner_pid": os.getpid()}), encoding="utf-8")
    (d / "_gateway_session.token").write_text("tok-live", encoding="utf-8")

    recovery.recover_at_startup(conn, workspace=tmp_path)

    assert calls == []
    assert d.exists()


def test_recovery_survives_a_gateway_that_is_not_there(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recovery runs before the gateway is guaranteed up — and on the
    version-skew path the one that IS up is about to be killed. A
    failed release must not stop the sweep: the claim then leaks, but
    the gateway's own probe still catches it, and a daemon that refuses
    to start over a best-effort POST is a worse failure than the leak."""
    import Tooling.pipeline as _pipeline

    def _boom(attempts_dir: Path) -> bool:
        raise OSError("connection refused")

    monkeypatch.setattr(_pipeline, "_release_session", _boom)
    d = _dead_spawn_dir(tmp_path, "pipe-dead", token="tok-abc")

    recovery.recover_at_startup(conn, workspace=tmp_path)

    assert not d.exists(), "the sweep must complete despite the failure"


def test_a_spawn_with_no_token_reports_nothing_to_hand_back(
    tmp_path: Path,
) -> None:
    """Not every attempts dir ever registered a session (intake-only
    turns, Strategist, Adversary). The count in the recovery line has
    to mean "slots", not "directories", or the operator reads a number
    that never drops when the leak is fixed."""
    d = _dead_spawn_dir(tmp_path, "pipe-no-tok", token=None)
    assert recovery._release_gateway_session(d) is False
