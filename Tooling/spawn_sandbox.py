"""Spawn-local filesystem sandbox for framework-managed file isolation.

Every framework-managed file mutation during a spawn is staged in a
sandbox copy under `attempts_dir/sandbox/`. The real path is committed
on success (via pipeline-specific `real_writes` callback) or rolled
back on failure. A daemon-startup sweep handles SIGKILL'd spawns that
bypassed the cleanup hook.

See `docs/archive/spawn_sandbox.md` for the full design rationale,
failure-mode coverage, and the BUG class this addresses.

Used by `pipeline/backward.py`, `pipeline/builder.py`, `verify.py`,
`library.py`. Coexists with `Tooling.agent.WorkArea` for now;
callers migrate in Phase 2-3 (per design §8).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


MANIFEST_NAME = "_manifest.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pid_alive(pid: int | None) -> bool:
    """Cross-platform 'is this pid running'. Returns False on any
    error / unknown state so callers fail-safe to 'dead'."""
    if pid is None or pid <= 0:
        return False
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except ImportError:
        pass
    if sys.platform == "win32":
        # Without psutil on Windows, best-effort via OpenProcess.
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return False
            try:
                # STILL_ACTIVE = 259; if GetExitCodeProcess gives
                # anything else, process has exited.
                exit_code = ctypes.c_ulong()
                ok = ctypes.windll.kernel32.GetExitCodeProcess(
                    handle, ctypes.byref(exit_code))
                if not ok:
                    return False
                return exit_code.value == 259
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ProcessLookupError):
        return False


class SpawnWorkspace:
    """Per-spawn working area + filesystem sandbox.

    Replaces `Tooling.agent.WorkArea` (Phase 2-3 migration). Owns:
      * `attempts_dir = workspace/.attempts/<pipeline_id>/`
      * `sandbox_dir  = attempts_dir/sandbox/`
      * snapshot of `real_paths` for rollback
      * commit/rollback semantics

    Lifecycle:
      with SpawnWorkspace(workspace, pipeline_id, real_paths) as ws:
          # Agent + framework writes go to ws.sandbox_path_for(real),
          # NEVER to real directly.
          ...
          ws.commit(real_writes=[(real_dest, bytes), ...])
          # If commit() never called, __exit__ rolls back.

    Invariant: for each real path P in `real_paths`, P's on-disk
    content after this context block is either P's pristine pre-spawn
    content, or content the caller explicitly wrote via commit().
    NEVER a partial mutation by the spawn process.

    See docs/archive/spawn_sandbox.md §2 (core invariant) and §3.5.
    """

    def __init__(self, workspace: Path, pipeline_id: str,
                 real_paths: Iterable[Path] = ()):
        self.workspace = Path(workspace).resolve()
        self.pipeline_id = pipeline_id
        self.attempts_dir = self.workspace / ".attempts" / pipeline_id
        self.sandbox_dir = self.attempts_dir / "sandbox"
        self._real_paths: list[Path] = [Path(p) for p in real_paths]
        self._manifest_path = self.sandbox_dir / MANIFEST_NAME
        self._committed = False
        # Legacy compat with WorkArea callers expecting `.attempts`.
        self.attempts = self.attempts_dir

    # ------------------------------------------------------------ enter

    def __enter__(self) -> "SpawnWorkspace":
        self.attempts_dir.mkdir(parents=True, exist_ok=True)
        # If a stale sandbox already exists (e.g. sweep missed it),
        # drop it; the new spawn owns this attempts_dir now.
        if self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "created_at": _now_iso(),
            "owner_pid": os.getpid(),
            "pipeline_id": self.pipeline_id,
            "committed": False,
            "real_paths": [],
        }
        for real in self._real_paths:
            content = real.read_bytes() if real.exists() else None
            sandbox = self._sandbox_for(real)
            sandbox.parent.mkdir(parents=True, exist_ok=True)
            if content is not None:
                sandbox.write_bytes(content)
            manifest["real_paths"].append({
                "real": str(real),
                "sandbox": str(sandbox),
                "sha_before": _sha256_hex(content) if content else None,
                "size_before": len(content) if content else 0,
                "existed_before": content is not None,
            })
        self._manifest_path.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        return self

    # ------------------------------------------------------------ paths

    def _sandbox_for(self, real: Path) -> Path:
        """Internal: sandbox snapshot path for a snapshotted real
        path. `sandbox/<filename>` holds the IMMUTABLE pre-spawn
        snapshot for rollback. Callers do not write here directly —
        sandbox is read-only snapshot storage, real-path mutations
        during the spawn happen on real (existing framework code,
        agent's LSP apply_edit write-through). Rollback restores
        real from this snapshot on non-commit exit.
        """
        return self.sandbox_dir / Path(real).name

    def restore_to_snapshot(self, real_path: Path) -> None:
        """Restore a single real_path from its sandbox snapshot bytes.

        Used by in-pipeline retry (backward.py / builder.py) to reset
        between retries so the next attempt sees pristine state. Same
        semantics as the existing `.backup` file restore those modules
        do today; this is the unified replacement.

        Idempotent on missing snapshot or missing manifest entry.
        """
        real_path = Path(real_path)
        sandbox = self._sandbox_for(real_path)
        if sandbox.exists():
            real_path.parent.mkdir(parents=True, exist_ok=True)
            real_path.write_bytes(sandbox.read_bytes())
        else:
            # No snapshot recorded for this path; check manifest for
            # existed_before=False case (path didn't exist on enter).
            if self._manifest_path.exists():
                try:
                    manifest = json.loads(
                        self._manifest_path.read_text(encoding="utf-8"))
                    for entry in manifest.get("real_paths", []):
                        if Path(entry["real"]) == real_path:
                            if not entry.get("existed_before"):
                                real_path.unlink(missing_ok=True)
                            return
                except (OSError, json.JSONDecodeError):
                    pass

    # ------------------------------------------------------------ commit

    def commit(self, real_writes: Iterable[tuple[Path, bytes]] = ()) -> None:
        """Atomically promote caller-supplied bytes to real paths.

        `real_writes` is the explicit list of (real_path, content)
        pairs to commit. Pipeline knows the translation between
        sandbox staging and final destinations (e.g. Backward agent
        writes `sandbox/patch.lean` but commits to
        `proofs/_strategy_s<id>.lean`; Builder commits `patch.lean`
        content to `goal_lean`).

        Real paths NOT in `real_writes` are left untouched (their
        pre-spawn content from snapshot is already what's on disk —
        we never wrote to them during the spawn).

        Per-file atomic via `os.replace`; multi-file commit is NOT
        cross-file transactional. If the daemon dies between file 1
        and file 2 of a multi-file commit, file 1 lands and file 2
        rolls back at next sweep. Pipelines should design idempotent
        commits (re-running on retry produces same outputs).

        Marks the sandbox as committed; sandbox dir survives until
        `__exit__` cleans it.
        """
        for real, content in real_writes:
            real = Path(real)
            real.parent.mkdir(parents=True, exist_ok=True)
            tmp = real.with_suffix(real.suffix + ".sb-tmp")
            tmp.write_bytes(content)
            os.replace(tmp, real)
        # Update manifest's committed flag so sweep won't roll back.
        manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        manifest["committed"] = True
        manifest["committed_at"] = _now_iso()
        manifest["committed_writes"] = [str(p) for p, _ in real_writes]
        self._manifest_path.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        self._committed = True

    # ------------------------------------------------------------ rollback / exit

    def rollback(self) -> None:
        """Restore each real_path from the sandbox snapshot bytes.

        We do not assume the spawn left real paths pristine. Existing
        framework code (backward.py / builder.py) writes through to
        real paths during agent LSP `apply_edit`. Sandbox is the
        snapshot-style safety net: if the pipeline doesn't reach
        commit (exception, abort, or daemon crash recovery), we
        rewrite each real path with its pre-spawn bytes from
        `sandbox/<filename>`.

        Idempotent. Safe to call multiple times.
        """
        if not self.sandbox_dir.exists():
            return
        manifest_path = self._manifest_path
        if manifest_path.exists():
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8"))
                for entry in manifest.get("real_paths", []):
                    real = Path(entry["real"])
                    sandbox = Path(entry["sandbox"])
                    if entry.get("existed_before"):
                        if sandbox.exists():
                            real.parent.mkdir(parents=True, exist_ok=True)
                            real.write_bytes(sandbox.read_bytes())
                    else:
                        # Real path didn't exist pre-spawn — if spawn
                        # created it, delete to restore "didn't exist".
                        if real.exists():
                            real.unlink(missing_ok=True)
            except (OSError, json.JSONDecodeError):
                pass  # Best-effort; manifest unreadable is forensic loss
        shutil.rmtree(self.sandbox_dir, ignore_errors=True)

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """SpawnWorkspace owns ONLY the sandbox/ subdir + manifest.
        attempts_dir lifecycle (mkdir, .drafts persistence, rmtree,
        gateway session release) stays with the caller's existing
        WorkArea / agent.py wrappers. Avoids dual-ownership conflicts
        — SpawnWorkspace is a snapshot guard inside attempts_dir, not
        a replacement for attempts_dir management.

        Behavior:
          * not committed → restore real paths from sandbox snapshots
          * committed     → no rollback needed
          * always        → drop the sandbox/ subdir
        """
        if not self._committed:
            self.rollback()
        if self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)
        return False


# ---------------------------------------------------------------- sweep

def sweep_orphan_sandboxes(workspace: Path) -> dict[str, int]:
    """Daemon-startup sweep. Cleans sandbox dirs whose owner daemon
    is dead. Returns counters for forensic logging.

    For each `<workspace>/.attempts/*/sandbox/`:
      * manifest missing/corrupt → delete sandbox dir
      * owner_pid alive → skip (concurrent daemon or current daemon's
        in-flight sandbox — sweep is startup-only so the latter
        shouldn't happen in practice, but defensive)
      * manifest.committed → safe to delete (commit landed, just stale
        sandbox dir)
      * manifest.committed=False → spawn died mid-flight. Real paths
        should already be pristine (we never wrote to them). SHA
        verify; warn on drift (out-of-sandbox writer bug).

    Idempotent. Safe to run multiple times.
    """
    workspace = Path(workspace).resolve()
    attempts_root = workspace / ".attempts"
    counters = {
        "scanned": 0,
        "deleted_committed": 0,
        "rolled_back": 0,
        "skipped_alive_owner": 0,
        "corrupt_manifest": 0,
        "drift_warnings": 0,
    }
    if not attempts_root.exists():
        return counters
    for sandbox_dir in attempts_root.glob("*/sandbox"):
        if not sandbox_dir.is_dir():
            continue
        counters["scanned"] += 1
        manifest_path = sandbox_dir / MANIFEST_NAME
        if not manifest_path.exists():
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            counters["corrupt_manifest"] += 1
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            counters["corrupt_manifest"] += 1
            continue
        # Owner daemon alive? Skip — could be concurrent daemon (operator
        # error) or our own (we shouldn't sweep our own, but defensive).
        owner_pid = manifest.get("owner_pid")
        if owner_pid and _pid_alive(owner_pid):
            counters["skipped_alive_owner"] += 1
            continue
        if manifest.get("committed"):
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            counters["deleted_committed"] += 1
            continue
        # Uncommitted: restore real paths from sandbox snapshots.
        # The orphan daemon was killed mid-spawn (operator taskkill or
        # crash); its in-process finally didn't run; real paths may be
        # drifted. We have the snapshot bytes on disk — use them.
        for entry in manifest.get("real_paths", []):
            real = Path(entry["real"])
            sandbox = Path(entry["sandbox"])
            sha_before = entry.get("sha_before")
            existed_before = entry.get("existed_before", True)
            current_sha = (_sha256_hex(real.read_bytes())
                           if real.exists() else None)
            drifted = (
                (existed_before and current_sha != sha_before)
                or (not existed_before and real.exists())
            )
            if drifted:
                print(
                    f"[sandbox-sweep] restoring {real} from snapshot "
                    f"(orphan daemon left drift)",
                    flush=True,
                )
                counters["drift_warnings"] += 1
                try:
                    if existed_before and sandbox.exists():
                        real.parent.mkdir(parents=True, exist_ok=True)
                        real.write_bytes(sandbox.read_bytes())
                    elif not existed_before:
                        real.unlink(missing_ok=True)
                except OSError as exc:
                    print(f"[sandbox-sweep] restore failed for {real}: "
                          f"{exc}", flush=True)
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        counters["rolled_back"] += 1
    return counters


def force_rollback_sandbox(sandbox_dir: Path) -> None:
    """Force-rollback a sandbox without going through __exit__.

    Used by fresh-rescue stage 2 entry (`_retry.py`) when the trapped
    spawn left a sandbox dir. The trapped spawn's `__exit__` would
    normally roll back, but trap-kill via SIGKILL skips it. Stage 2
    can't safely re-snapshot until real paths are confirmed pristine.

    Same SHA-drift check as `sweep_orphan_sandboxes` but operates on a
    specific sandbox dir; warns on drift but does not abort.
    """
    sandbox_dir = Path(sandbox_dir)
    if not sandbox_dir.exists():
        return
    manifest_path = sandbox_dir / MANIFEST_NAME
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not manifest.get("committed"):
                for entry in manifest.get("real_paths", []):
                    real = Path(entry["real"])
                    sha_before = entry.get("sha_before")
                    if real.exists() and sha_before:
                        if _sha256_hex(real.read_bytes()) != sha_before:
                            print(
                                f"[sandbox-force-rollback] WARNING drift "
                                f"on {real} during takeover entry",
                                flush=True,
                            )
        except (OSError, json.JSONDecodeError):
            pass
    shutil.rmtree(sandbox_dir, ignore_errors=True)
