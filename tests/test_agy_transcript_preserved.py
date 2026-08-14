"""An agy spawn's conversation must outlive its home.

agy's home is per-spawn because the home IS the capability envelope
(permissions + the gateway session token), and it lives under
`.attempts/<pid>/`, which `WorkArea.__exit__` rmtree's. So the store
that records what the agent actually did dies with the attempt unless
something copies it out first.

WHAT IT COST: asked on 2026-08-15 why the agy formalizer burned 74x the
fresh input of the claude one, the answer was in agy's own per-turn
store — and of 214 surviving conversations, 122 were adversary, 43
strategist, and none a formalizer. Every survivor predated the
per-spawn home (2026-08-02); the expensive spawns were 08-07 and 08-10.
The question could not be answered from this side at all.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.llm import antigravity_cli as agy


def _home_with_conversation(home: Path, name: str = "abc123",
                            leave_open: bool = False):
    """Returns the db path, and the open connection when asked.

    Holding it open is what reproduces production: sqlite folds the WAL
    back and deletes it when the LAST connection closes, so a clean exit
    leaves none — but the spawns whose transcript anyone wants are the
    ones killed at the timeout wall, and those leave the tail of the
    conversation in the sidecar. Every surviving store on this box has a
    `-wal` beside it."""
    conv = home / ".gemini" / "antigravity-cli" / "conversations"
    conv.mkdir(parents=True, exist_ok=True)
    db = conv / f"{name}.db"
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE steps (idx INTEGER, step_payload BLOB)")
    con.execute("INSERT INTO steps VALUES (0, ?)", (b"the agent's turn",))
    con.commit()
    if leave_open:
        return db, con
    con.close()
    return db, None


class _Req:
    def __init__(self, attempts_dir: Path):
        self.attempts_dir = attempts_dir


def test_the_conversation_is_copied_out_of_the_home(tmp_path: Path):
    workspace = tmp_path / "ws"
    attempts = workspace / ".attempts" / "pipe-7"
    attempts.mkdir(parents=True)
    home = attempts / "_agy_home"
    _home_with_conversation(home)

    agy._preserve_transcript(_Req(attempts), home)

    dest = agy.transcript_dir(workspace, "pipe-7")
    assert (dest / "abc123.db").is_file(), "the conversation was not saved"


def test_the_wal_travels_with_the_database(tmp_path: Path):
    """agy writes in WAL mode and the tail of a conversation can sit
    entirely in the sidecar. A `.db` lifted on its own opens as
    `database disk image is malformed` — measured 2026-08-15 on the
    first surviving store opened, before this helper existed."""
    workspace = tmp_path / "ws"
    attempts = workspace / ".attempts" / "pipe-8"
    attempts.mkdir(parents=True)
    home = attempts / "_agy_home"
    db, con = _home_with_conversation(home, leave_open=True)
    assert db.with_suffix(".db-wal").is_file(), "fixture wrote no WAL"

    agy._preserve_transcript(_Req(attempts), home)
    con.close()

    dest = agy.transcript_dir(workspace, "pipe-8")
    assert (dest / "abc123.db-wal").is_file(), "the WAL was left behind"
    con = sqlite3.connect(dest / "abc123.db")
    assert con.execute("SELECT COUNT(*) FROM steps").fetchone()[0] == 1
    con.close()


def test_one_unreadable_conversation_does_not_take_the_others(
        tmp_path: Path, capsys, monkeypatch):
    """Best-effort per artifact, never all-or-nothing — the lesson
    `codex_cli._preserve_transcript` records in the same words."""
    workspace = tmp_path / "ws"
    attempts = workspace / ".attempts" / "pipe-9"
    attempts.mkdir(parents=True)
    home = attempts / "_agy_home"
    _home_with_conversation(home, "aaa")
    _home_with_conversation(home, "zzz")

    real = agy.shutil.copyfile

    def _flaky(src, dst, *a, **k):
        if "aaa" in Path(src).name:
            raise OSError("locked by the vendor process")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(agy.shutil, "copyfile", _flaky)
    agy._preserve_transcript(_Req(attempts), home)

    dest = agy.transcript_dir(workspace, "pipe-9")
    assert (dest / "zzz.db").is_file(), "one bad copy took a good one down"
    assert "not preserved" in capsys.readouterr().out


def test_nothing_to_save_is_silent(tmp_path: Path, capsys):
    """A spawn that died before agy opened a conversation has no
    transcript, which is not an error and must not print like one."""
    workspace = tmp_path / "ws"
    attempts = workspace / ".attempts" / "pipe-10"
    (attempts / "_agy_home").mkdir(parents=True)

    agy._preserve_transcript(_Req(attempts), attempts / "_agy_home")

    assert not agy.transcript_dir(workspace, "pipe-10").exists()
    assert capsys.readouterr().out == ""


def test_the_capability_envelope_is_not_copied_out(tmp_path: Path):
    """The home dies on purpose: it carries the spawn's permission
    surface and its gateway session token. Transcript survives, envelope
    does not."""
    workspace = tmp_path / "ws"
    attempts = workspace / ".attempts" / "pipe-11"
    attempts.mkdir(parents=True)
    home = attempts / "_agy_home"
    _home_with_conversation(home)
    (home / ".gemini" / "antigravity-cli" / "settings.json").write_text(
        '{"permissions": {"allow": ["read_file(**)"]}}', encoding="utf-8")
    (home / ".gemini" / "config").mkdir(parents=True, exist_ok=True)
    (home / ".gemini" / "config" / "mcp_config.json").write_text(
        '{"mcpServers": {"lsp": {"args": ["--session", "SECRET"]}}}',
        encoding="utf-8")

    agy._preserve_transcript(_Req(attempts), home)

    dest = agy.transcript_dir(workspace, "pipe-11")
    landed = {p.name for p in dest.rglob("*")}
    assert "settings.json" not in landed
    assert "mcp_config.json" not in landed


def test_spawn_preserves_on_every_exit_path(monkeypatch, tmp_path: Path):
    """The paths that most need a transcript are the ones that return
    early — the timeout, and the spawn killed mid-thought — so the copy
    is the outer `finally`, not a line at the end of the happy path."""
    calls: list = []
    monkeypatch.setattr(agy, "_preserve_transcript",
                        lambda req, home: calls.append(home))
    monkeypatch.setattr(agy.AntigravityCliProvider, "_spawn_inner",
                        lambda self, req, box: (box.append(tmp_path),
                                                1 / 0)[1])
    with pytest.raises(ZeroDivisionError):
        agy.AntigravityCliProvider().spawn(_Req(tmp_path))
    assert calls == [tmp_path], "an exception skipped preservation"
