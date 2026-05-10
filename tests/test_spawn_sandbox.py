"""Spawn sandbox foundation tests — Phase 1.

Covers:
  * enter snapshots real paths
  * commit promotes caller-named bytes to real paths
  * rollback (uncommitted exit) leaves real paths pristine
  * exception inside `with` block triggers rollback
  * sweep cleans uncommitted sandboxes from dead owners
  * sweep skips sandboxes with alive owner_pid
  * sweep deletes committed sandboxes
  * sweep warns on SHA drift (out-of-sandbox writer)
  * force_rollback_sandbox for fresh-rescue takeover entry
  * append-on-enter when stale sandbox already exists

See docs/dev/spawn_sandbox.md §3 + §4 for the design rationale.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from Tooling import spawn_sandbox
from Tooling.spawn_sandbox import (
    MANIFEST_NAME,
    SpawnWorkspace,
    force_rollback_sandbox,
    sweep_orphan_sandboxes,
)


# ---------------------------------------------------------------- helpers

def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _seed(p: Path, content: bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------- enter

def test_enter_creates_attempts_and_sandbox_dirs(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_goal.lean", b"theorem g := by sorry\n")
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        assert ws.attempts_dir.exists()
        assert ws.sandbox_dir.exists()
        assert (ws.sandbox_dir / MANIFEST_NAME).exists()


def test_enter_snapshots_real_path_into_sandbox(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_goal.lean", b"original\n")
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        # Internal: snapshot copy lives at sandbox/<filename>.
        sb_copy = ws._sandbox_for(real)
        assert sb_copy.exists()
        assert sb_copy.read_bytes() == b"original\n"


def test_enter_manifest_records_sha_and_size(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_goal.lean", b"abc123\n")
    expected_sha = hashlib.sha256(b"abc123\n").hexdigest()
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        manifest = json.loads((ws.sandbox_dir / MANIFEST_NAME).read_text())
        assert manifest["committed"] is False
        assert manifest["owner_pid"] == os.getpid()
        assert manifest["pipeline_id"] == "pid-1"
        entry = manifest["real_paths"][0]
        assert entry["sha_before"] == expected_sha
        assert entry["size_before"] == 7
        assert entry["existed_before"] is True


def test_enter_with_nonexistent_real_path_records_existed_before_false(
    tmp_path: Path,
) -> None:
    not_yet = tmp_path / "Problems/p/proofs/L_goal.lean"
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[not_yet]) as ws:
        manifest = json.loads((ws.sandbox_dir / MANIFEST_NAME).read_text())
        entry = manifest["real_paths"][0]
        assert entry["existed_before"] is False
        assert entry["sha_before"] is None
        assert not ws._sandbox_for(not_yet).exists()


def test_enter_with_stale_sandbox_drops_and_recreates(tmp_path: Path) -> None:
    """If an attempts_dir already has a sandbox/ from a prior pipeline
    run on the same pid (sweep should have cleaned but defensive),
    re-entering drops the stale dir."""
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"v2\n")
    # Pre-create stale sandbox
    attempts = tmp_path / ".attempts" / "pid-1"
    stale = attempts / "sandbox"
    stale.mkdir(parents=True)
    (stale / "junk").write_bytes(b"old")
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        assert not (ws.sandbox_dir / "junk").exists()
        assert (ws.sandbox_dir / MANIFEST_NAME).exists()


# ---------------------------------------------------------------- commit

def test_commit_writes_caller_named_bytes_to_real_path(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"v1\n")
    dest = tmp_path / "Problems/p/proofs/L_g.lean"
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        ws.commit(real_writes=[(dest, b"v2 committed\n")])
    assert dest.read_bytes() == b"v2 committed\n"


def test_commit_can_target_path_outside_real_paths(tmp_path: Path) -> None:
    """Backward writes to scratch_path which wasn't snapshotted as a
    real_path (since scratch doesn't pre-exist). commit() accepts
    these and writes through."""
    real = _seed(tmp_path / "Problems/p/proofs/L_main.lean", b"main stub\n")
    scratch = tmp_path / "Problems/p/proofs/_strategy_s1.lean"  # not yet exists
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        ws.commit(real_writes=[(scratch, b"strategy content\n")])
    assert scratch.read_bytes() == b"strategy content\n"


def test_commit_marks_manifest_committed(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"v1\n")
    ws = SpawnWorkspace(tmp_path, "pid-1", real_paths=[real])
    ws.__enter__()
    try:
        ws.commit(real_writes=[(real, b"v2\n")])
        # Sandbox dir still exists at this moment (cleanup happens on __exit__)
        manifest = json.loads((ws.sandbox_dir / MANIFEST_NAME).read_text())
        assert manifest["committed"] is True
        assert "committed_at" in manifest
    finally:
        ws.__exit__(None, None, None)


def test_commit_is_atomic_per_file(tmp_path: Path) -> None:
    """If commit writes via .sb-tmp + os.replace, mid-write should
    never leave the real file half-written. We assert by checking
    no .sb-tmp lingers after a successful commit."""
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"v1\n")
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        ws.commit(real_writes=[(real, b"v2\n")])
    # No .sb-tmp leftover
    leftovers = list(real.parent.glob("*.sb-tmp"))
    assert leftovers == []


# ---------------------------------------------------------------- rollback

def test_exit_without_commit_leaves_real_path_unchanged(
    tmp_path: Path,
) -> None:
    """Real path untouched during spawn → rollback no-ops, real keeps
    pristine. Rollback's restore step writes snapshot bytes back, but
    the bytes match pristine so it's effectively idempotent."""
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"pristine\n")
    sha_before = _sha(real)
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]):
        pass
    assert real.read_bytes() == b"pristine\n"
    assert _sha(real) == sha_before


def test_rollback_restores_real_path_if_caller_drifted_it(
    tmp_path: Path,
) -> None:
    """Pragmatic mode: framework code may write directly to real path
    during spawn (existing backward.py / builder.py via LSP apply_edit
    write-through). Rollback restores real path from snapshot bytes."""
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"pristine\n")
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        # Simulate LSP apply_edit write-through to real
        real.write_text("drifted by agent edit\n", encoding="utf-8")
    # Rollback restored
    assert real.read_bytes() == b"pristine\n"


def test_rollback_restores_real_path_deleted_during_spawn(
    tmp_path: Path,
) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"pristine\n")
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        real.unlink()  # Simulate framework deleting a snapshotted real
    assert real.read_bytes() == b"pristine\n"


def test_rollback_removes_real_path_if_didnt_exist_before(
    tmp_path: Path,
) -> None:
    not_yet = tmp_path / "Problems/p/proofs/L_g.lean"
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[not_yet]) as ws:
        not_yet.parent.mkdir(parents=True, exist_ok=True)
        not_yet.write_text("created by spawn\n")
    assert not not_yet.exists()


def test_exception_in_with_block_triggers_rollback(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"pristine\n")

    class _MyError(RuntimeError):
        pass

    with pytest.raises(_MyError):
        with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
            real.write_text("halfway edit\n")  # drift real
            raise _MyError("simulated crash")
    assert real.read_bytes() == b"pristine\n"


def test_restore_to_snapshot_rewrites_real_from_sandbox(
    tmp_path: Path,
) -> None:
    """In-pipeline retry helper: between retries within one pipeline,
    reset real path to its pre-pipeline snapshot. Replaces the old
    `.backup` file mechanism in backward.py / builder.py."""
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"pristine\n")
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        # Simulate retry 1: agent writes garbage via LSP
        real.write_text("retry 1 garbage\n")
        # Retry helper resets for retry 2
        ws.restore_to_snapshot(real)
        assert real.read_bytes() == b"pristine\n"
        # Retry 2: another write
        real.write_text("retry 2 garbage\n")
        ws.restore_to_snapshot(real)
        assert real.read_bytes() == b"pristine\n"


def test_restore_to_snapshot_handles_path_that_didnt_exist_before(
    tmp_path: Path,
) -> None:
    """If real didn't exist on enter and spawn created it, restore
    means delete (existed_before=False)."""
    not_yet = tmp_path / "Problems/p/proofs/L_g.lean"
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[not_yet]) as ws:
        not_yet.parent.mkdir(parents=True, exist_ok=True)
        not_yet.write_text("created by retry\n")
        ws.restore_to_snapshot(not_yet)
        assert not not_yet.exists()


def test_exit_after_commit_cleans_sandbox_dir(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"v1\n")
    with SpawnWorkspace(tmp_path, "pid-1", real_paths=[real]) as ws:
        ws.commit(real_writes=[(real, b"v2\n")])
        sb_dir = ws.sandbox_dir
        attempts = ws.attempts_dir
    # After __exit__, sandbox/ is dropped. attempts_dir itself is
    # NOT removed — that's WorkArea's responsibility.
    assert not sb_dir.exists()
    assert attempts.exists()


# ---------------------------------------------------------------- sweep

def _make_stale_sandbox(workspace: Path, pid_id: str,
                       real: Path, *, committed: bool,
                       owner_pid: int | None = 0) -> Path:
    """Manually fabricate a sandbox dir as if a prior daemon left it."""
    attempts = workspace / ".attempts" / pid_id
    sb = attempts / "sandbox"
    sb.mkdir(parents=True, exist_ok=True)
    real_content = real.read_bytes() if real.exists() else b""
    (sb / real.name).write_bytes(real_content)
    manifest = {
        "created_at": "2026-01-01T00:00:00+00:00",
        "owner_pid": owner_pid if owner_pid is not None else 1,
        "pipeline_id": pid_id,
        "committed": committed,
        "real_paths": [{
            "real": str(real),
            "sandbox": str(sb / real.name),
            "sha_before": hashlib.sha256(real_content).hexdigest() if real_content else None,
            "size_before": len(real_content),
            "existed_before": real.exists(),
        }],
    }
    (sb / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))
    return sb


def test_sweep_deletes_uncommitted_sandbox_from_dead_owner(
    tmp_path: Path,
) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"pristine\n")
    sb = _make_stale_sandbox(tmp_path, "pid-stale", real,
                              committed=False, owner_pid=0)
    counters = sweep_orphan_sandboxes(tmp_path)
    assert not sb.exists()
    assert counters["rolled_back"] == 1
    assert real.read_bytes() == b"pristine\n"


def test_sweep_deletes_committed_sandbox(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"committed-result\n")
    sb = _make_stale_sandbox(tmp_path, "pid-old", real,
                              committed=True, owner_pid=0)
    counters = sweep_orphan_sandboxes(tmp_path)
    assert not sb.exists()
    assert counters["deleted_committed"] == 1


def test_sweep_skips_sandbox_with_alive_owner(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"pristine\n")
    # Use current pid as "owner" — it's alive (this very process).
    sb = _make_stale_sandbox(tmp_path, "pid-mine", real,
                              committed=False, owner_pid=os.getpid())
    counters = sweep_orphan_sandboxes(tmp_path)
    assert sb.exists()
    assert counters["skipped_alive_owner"] == 1


def test_sweep_handles_corrupt_manifest(tmp_path: Path) -> None:
    attempts = tmp_path / ".attempts" / "pid-corrupt"
    sb = attempts / "sandbox"
    sb.mkdir(parents=True)
    (sb / MANIFEST_NAME).write_text("{ not valid json")
    counters = sweep_orphan_sandboxes(tmp_path)
    assert not sb.exists()
    assert counters["corrupt_manifest"] == 1


def test_sweep_handles_missing_manifest(tmp_path: Path) -> None:
    attempts = tmp_path / ".attempts" / "pid-nomanifest"
    sb = attempts / "sandbox"
    sb.mkdir(parents=True)
    (sb / "stray").write_bytes(b"junk")
    counters = sweep_orphan_sandboxes(tmp_path)
    assert not sb.exists()
    assert counters["corrupt_manifest"] == 1


def test_sweep_restores_drifted_real_from_snapshot(
    tmp_path: Path, capsys,
) -> None:
    """Uncommitted sandbox + drifted real → sweep restores real from
    sandbox snapshot bytes. Recovery path for daemon crash mid-spawn."""
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"original\n")
    sb = _make_stale_sandbox(tmp_path, "pid-drift", real,
                              committed=False, owner_pid=0)
    # Simulate orphan-daemon mid-spawn drift on real
    real.write_bytes(b"agent partial edit\n")
    counters = sweep_orphan_sandboxes(tmp_path)
    assert real.read_bytes() == b"original\n"  # restored
    captured = capsys.readouterr()
    assert "restoring" in captured.out
    assert counters["drift_warnings"] == 1


def test_sweep_restores_deleted_real_from_snapshot(
    tmp_path: Path, capsys,
) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"original\n")
    _make_stale_sandbox(tmp_path, "pid-del", real,
                        committed=False, owner_pid=0)
    real.unlink()
    counters = sweep_orphan_sandboxes(tmp_path)
    assert real.read_bytes() == b"original\n"
    assert counters["drift_warnings"] == 1


def test_sweep_no_attempts_dir_is_noop(tmp_path: Path) -> None:
    counters = sweep_orphan_sandboxes(tmp_path)
    assert counters["scanned"] == 0


def test_sweep_idempotent(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"v\n")
    _make_stale_sandbox(tmp_path, "pid-x", real,
                         committed=False, owner_pid=0)
    c1 = sweep_orphan_sandboxes(tmp_path)
    c2 = sweep_orphan_sandboxes(tmp_path)
    assert c1["rolled_back"] == 1
    assert c2["scanned"] == 0


# ---------------------------------------------------------------- force_rollback (fresh-rescue takeover)

def test_force_rollback_drops_sandbox(tmp_path: Path) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"pristine\n")
    sb = _make_stale_sandbox(tmp_path, "pid-trap", real,
                              committed=False, owner_pid=0)
    force_rollback_sandbox(sb)
    assert not sb.exists()
    assert real.read_bytes() == b"pristine\n"


def test_force_rollback_warns_on_drift(tmp_path: Path, capsys) -> None:
    real = _seed(tmp_path / "Problems/p/proofs/L_g.lean", b"original\n")
    sb = _make_stale_sandbox(tmp_path, "pid-trap", real,
                              committed=False, owner_pid=0)
    real.write_bytes(b"drifted\n")
    force_rollback_sandbox(sb)
    captured = capsys.readouterr()
    assert "drift" in captured.out.lower()


def test_force_rollback_idempotent_on_missing_dir(tmp_path: Path) -> None:
    """Calling force_rollback on a non-existent sandbox should not raise."""
    force_rollback_sandbox(tmp_path / "no-such-dir")  # no error


# ---------------------------------------------------------------- _pid_alive

def test_pid_alive_returns_true_for_self() -> None:
    assert spawn_sandbox._pid_alive(os.getpid()) is True


def test_pid_alive_returns_false_for_zero_or_none() -> None:
    assert spawn_sandbox._pid_alive(None) is False
    assert spawn_sandbox._pid_alive(0) is False
    assert spawn_sandbox._pid_alive(-1) is False


def test_pid_alive_returns_false_for_dead_pid() -> None:
    # PID 999999 is almost certainly not alive (max PID is usually 32768
    # on Linux, ~64k on Win).
    assert spawn_sandbox._pid_alive(999999) is False
