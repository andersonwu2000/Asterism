"""Sign-off signature (v27): the approval records who signed, when,
with machine-captured evidence, sealing exactly the reviewed content.
Owner design (2026-07-11): name = the operator's claim, evidence = the
machine's observation, hash = the content seal; revoked judgments
(reject / rollback) must not keep wearing the seal.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from Tooling.state import db


def _open(tmp_path: Path):
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    return conn


def _add_problem(conn, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, ?, ?)", (name, f"Problems/{name}/Manifest.md", db.now()))
    conn.commit()


def test_signoff_record_roundtrip_and_revoke(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    _add_problem(conn)
    assert db.get_ingest_signoff(conn, "p") is None  # predates / unsigned
    rec = {"name": "Anderson", "at": db.now(), "snapshot_sha": "abc",
           "evidence": {"claude_email": "a@b", "os_user": "u", "host": "h"}}
    db.set_ingest_signoff(conn, "p", rec)
    assert db.get_ingest_signoff(conn, "p") == rec
    db.set_ingest_signoff(conn, "p", None)  # revoke
    assert db.get_ingest_signoff(conn, "p") is None


def test_approve_signs_and_reject_revokes(tmp_path: Path, monkeypatch) -> None:
    """cmd_approve_ingest writes the full record (name + captured
    evidence + snapshot seal); cmd_reject_ingest strips the seal."""
    from Tooling.core import cli as _cli
    conn = _open(tmp_path)
    _add_problem(conn)
    db.set_ingest_signoff_pending(conn, "p", True)
    # v29 problem FSM: a signoff-pending problem is in 'ingest_signoff'
    # (production sets both at the Ingest commit; this fixture stamps
    # the carrier directly, so stamp the state alongside).
    conn.execute("UPDATE problems SET state='ingest_signoff'"
                 " WHERE name='p'")
    db.set_review_snapshot(conn, "p", '{"deliverables": []}')
    conn.commit()
    conn.close()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cli, "_claude_login_email", lambda: "acct@x.y")

    rc = _cli.cmd_approve_ingest(
        argparse.Namespace(problem="p", signer="  Anderson Wu "))
    assert rc == 0
    conn = _open(tmp_path)
    rec = db.get_ingest_signoff(conn, "p")
    assert rec is not None
    assert rec["name"] == "Anderson Wu"          # trimmed claim
    assert rec["evidence"]["claude_email"] == "acct@x.y"
    assert rec["evidence"]["os_user"] and rec["evidence"]["host"]
    expect_sha = hashlib.sha256(
        b'{"deliverables": []}').hexdigest()
    assert rec["snapshot_sha"] == expect_sha     # seals what was shown

    # reject revokes: back to proving, no lingering seal
    db.set_ingest_signoff_pending(conn, "p", True)
    conn.execute("UPDATE problems SET state='ingest_signoff'"
                 " WHERE name='p'")
    conn.commit()
    conn.close()
    rc = _cli.cmd_reject_ingest(
        argparse.Namespace(problem="p", reason="not done"))
    assert rc == 0
    conn = _open(tmp_path)
    assert db.get_ingest_signoff(conn, "p") is None


def test_approve_enqueues_librarian_iff_library_flag(
        tmp_path: Path, monkeypatch) -> None:
    """2026-07-18 gate retirement: the signature carries the Library
    decision (serve writes the flag through the settings chokepoint
    before calling approve). Signing with library:false must NOT start
    a harvest — the old unconditional enqueue was a BUG3-class bypass
    (the consumer gate only checks the pending flag, which approval
    just cleared)."""
    from Tooling.core import cli as _cli
    from Tooling.state import settings as _settings

    def _pause(conn, name):
        db.set_ingest_signoff_pending(conn, name, True)
        conn.execute("UPDATE problems SET state='ingest_signoff'"
                     " WHERE name=?", (name,))
        conn.commit()

    conn = _open(tmp_path)
    _add_problem(conn, "p")
    _add_problem(conn, "q")
    _pause(conn, "p")
    _pause(conn, "q")
    _settings.write(conn, "p", "library", False)
    _settings.write(conn, "q", "library", True)
    conn.close()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cli, "_claude_login_email", lambda: "a@x.y")

    assert _cli.cmd_approve_ingest(
        argparse.Namespace(problem="p", signer="A")) == 0
    assert _cli.cmd_approve_ingest(
        argparse.Namespace(problem="q", signer="A")) == 0
    conn = _open(tmp_path)
    rows = conn.execute(
        "SELECT problem FROM queue WHERE kind='Librarian'").fetchall()
    assert [str(r["problem"]) for r in rows] == ["q"]
    conn.close()


def test_seal_breaks_when_snapshot_changes(tmp_path: Path) -> None:
    """signoff_with_seal: seal_ok flips false the moment the stored
    snapshot no longer matches what was signed — the reader sees the
    drift instead of a silently meaningless vouch."""
    from Tooling.serve import data as _data
    conn = _open(tmp_path)
    _add_problem(conn)
    db.set_review_snapshot(conn, "p", "CONTENT-1")
    sha = hashlib.sha256(b"CONTENT-1").hexdigest()
    db.set_ingest_signoff(conn, "p", {
        "name": "A", "at": db.now(), "snapshot_sha": sha,
        "evidence": {"claude_email": None, "os_user": "u", "host": "h"}})
    out = _data.signoff_with_seal(conn, "p")
    assert out is not None and out["seal_ok"] is True

    db.set_review_snapshot(conn, "p", "CONTENT-2 (refreshed)")
    out = _data.signoff_with_seal(conn, "p")
    assert out is not None and out["seal_ok"] is False

    # unsigned problems stay None (no fake records)
    db.set_ingest_signoff(conn, "p", None)
    assert _data.signoff_with_seal(conn, "p") is None
