"""F46 — defense against claude.exe instant-fail loops.

A spawn that returns rc≠0 in <10s wall-clock is almost certainly an
infra fault (CLI crash on launch, prompt parser reject, cwd unreachable,
transient network) rather than an agent error. Three things must work:

1. Provider writes captured stderr to `attempts_dir/_spawn.stderr` so
   the cause is no longer black-boxed.
2. Pipeline reclassifies short rc≠0 calls as `spawn_fast_fail` and
   includes the stderr tail in `failure_detail`.
3. cascade_one detects spawn_fast_fail rows via DB lookup and skips
   `increment_goal_attempts` so a transient infra blip doesn't burn
   the goal's attempts cap.

Daemon-loop cool-down + global-bound counter are exercised manually in
production (no easy unit harness for the threaded loop); the unit-level
contract here is sufficient to keep the regression from reappearing.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
import pytest

from Tooling.state import db
from Tooling import pipeline as _pipeline
from Tooling.core.dispatcher import cascade_one


# ---------------------------------------------------------------------
# 1. Provider stderr capture
# ---------------------------------------------------------------------

class _FakePopen:
    """Stand-in for subprocess.Popen — supports communicate(timeout=...)
    and poll() that the watchdog inspects. Constructed via factory
    closures in tests so the mock returns the desired (rc, stdout,
    stderr) triple or raises TimeoutExpired."""
    def __init__(self, *, rc: int = 0, stdout: str = "",
                 stderr: str = "", raise_timeout: bool = False) -> None:
        self._rc = rc
        self._stdout = stdout
        self._stderr = stderr
        self._raise_timeout = raise_timeout
        self.returncode: int | None = None

    def communicate(self, input=None, timeout: float | None = None):
        import subprocess
        if self._raise_timeout:
            # Mirror subprocess.run's TimeoutExpired path: caller (claude
            # CLI provider) calls proc.kill() then communicate() again
            # to drain — that second call returns the captured streams.
            self._raise_timeout = False
            raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
        self.returncode = self._rc
        return self._stdout, self._stderr

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def terminate(self):
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


def test_claude_spawn_writes_stderr_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """rc≠0 → write `attempts_dir/_spawn.stderr` with the captured
    stderr. Skip on rc=0 to keep the sandbox tidy."""
    from Tooling.llm import claude_cli, base
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(
            rc=1, stderr="claude: prompt parse error at line 3"))
    (tmp_path / "p.md").write_text("body", encoding="utf-8")
    p = claude_cli.ClaudeCliProvider()
    p.spawn(base.LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    sf = tmp_path / "_spawn.stderr"
    assert sf.exists()
    body = sf.read_text(encoding="utf-8")
    assert "rc=1" in body
    assert "prompt parse error" in body


def test_claude_spawn_skips_stderr_file_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """rc=0 → don't write _spawn.stderr (avoid clutter)."""
    from Tooling.llm import claude_cli, base
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(rc=0, stdout="ok"))
    (tmp_path / "p.md").write_text("body", encoding="utf-8")
    p = claude_cli.ClaudeCliProvider()
    p.spawn(base.LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    assert not (tmp_path / "_spawn.stderr").exists()


def test_claude_spawn_writes_timeout_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Subprocess timeout (full wall hit) → rc=124, synthetic
    _spawn.stderr. Watchdog stuck-kill returns rc=128 instead and is
    covered by test_claude_spawn_stuck_thinking."""
    from Tooling.llm import claude_cli, base
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "Popen",
        lambda *a, **kw: _FakePopen(raise_timeout=True))
    (tmp_path / "p.md").write_text("body", encoding="utf-8")
    p = claude_cli.ClaudeCliProvider()
    rc = p.spawn(base.LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=1,
    ))
    assert rc == 124
    body = (tmp_path / "_spawn.stderr").read_text(encoding="utf-8")
    assert "TimeoutExpired" in body


def test_gemini_spawn_writes_stderr_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Mirror behavior in gemini_cli."""
    import subprocess as _sub
    from Tooling.llm import gemini_cli, base
    monkeypatch.setattr(gemini_cli.shutil, "which", lambda _: "/fake/gemini")
    monkeypatch.setattr(
        gemini_cli.subprocess, "run",
        lambda *a, **kw: _sub.CompletedProcess(
            args=a[0], returncode=2, stdout="",
            stderr="gemini: 401 Unauthorized"))
    (tmp_path / "p.md").write_text("body", encoding="utf-8")
    p = gemini_cli.GeminiCliProvider()
    p.spawn(base.LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    body = (tmp_path / "_spawn.stderr").read_text(encoding="utf-8")
    assert "rc=2" in body
    assert "401 Unauthorized" in body


# ---------------------------------------------------------------------
# 2. Pipeline classifies spawn_fast_fail
# ---------------------------------------------------------------------

def test_spawn_failure_classifies_fast_as_spawn_fast_fail(
    tmp_path: Path,
) -> None:
    """Spawn duration < SPAWN_FAST_FAIL_SEC (10s) and rc≠0 → reason
    is `spawn_fast_fail`, not `agent_rc_nonzero`."""
    reason, detail = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=2.3)
    assert reason == "spawn_fast_fail"
    assert "fast-fail" in detail
    assert "2.3s" in detail


def test_spawn_failure_classifies_timeout_as_agent_timeout(
    tmp_path: Path,
) -> None:
    """rc=124 (SIGKILL after WORKER_TIMEOUT_SEC) → `agent_timeout`."""
    reason, _ = _pipeline._spawn_failure(
        rc=124, attempts_dir=tmp_path, spawn_dur=600.0)
    assert reason == "agent_timeout"


def test_spawn_failure_classifies_slow_nontimeout_as_unclassified(
    tmp_path: Path,
) -> None:
    """rc≠0 and rc≠124, wall ≥ 10s → `unclassified_spawn_failure`.

    Was `agent_rc_nonzero` (charged to the goal) until the 2026-08-08
    owner ruling: an unrecognised rc cannot tell us whether the worker
    got a fair chance, and guessing "the agent's fault" is what let a
    dying workstation shove five healthy goals into strategist review."""
    reason, _ = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=15.0)
    assert reason == "unclassified_spawn_failure"


def test_spawn_failure_names_a_network_death(tmp_path: Path) -> None:
    """stderr naming a transport failure → `provider_network`, whatever
    the duration says (2026-08-18: the 08-17 outage's deaths ran 37s to
    454s — both sides of the fast-fail line — all carrying the same
    `stream disconnected` prose, and twelve of them tripped the
    unclassified breaker into an rc=2 exit needing an operator)."""
    (tmp_path / "_spawn.stderr").write_text(
        "rc=1\nstream disconnected before completion: error sending "
        "request for url", encoding="utf-8")
    reason, detail = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=37.0)
    assert reason == "provider_network"
    assert "network failure" in detail
    # ...and it outranks the fast-fail duration heuristic.
    reason, _ = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=2.0)
    assert reason == "provider_network"


def test_spawn_timeout_outranks_the_network_prose(tmp_path: Path) -> None:
    """rc=124 is the framework's own SIGKILL — unambiguous, and it wins
    over any stderr prose (a timed-out worker may well have logged a
    transient network line on the way)."""
    (tmp_path / "_spawn.stderr").write_text(
        "rc=124\nconnection reset by peer", encoding="utf-8")
    reason, _ = _pipeline._spawn_failure(
        rc=124, attempts_dir=tmp_path, spawn_dur=1800.0)
    assert reason == "agent_timeout"


def test_spawn_failure_includes_stderr_tail(tmp_path: Path) -> None:
    """When _spawn.stderr exists, its first ~600 chars are folded into
    failure_detail so dead_attempts isn't a black box."""
    (tmp_path / "_spawn.stderr").write_text(
        "rc=1\nclaude: cannot read file foo/bar.md", encoding="utf-8")
    _, detail = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=1.5)
    assert "cannot read file foo/bar.md" in detail


def test_spawn_failure_handles_missing_stderr_file(tmp_path: Path) -> None:
    """No _spawn.stderr (provider didn't write it for some reason) →
    fall back to just `agent rc=N` text. Must not raise."""
    reason, detail = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=2.0)
    assert reason == "spawn_fast_fail"
    assert "rc=1" in detail


# ---------------------------------------------------------------------
# 3. cascade_one skips increment for spawn_fast_fail
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection, *, problem: str = "p") -> int:
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done) VALUES (?, ?, 1)",
        (problem, db.now()),
    )
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root",
    )


def _record_dead_attempt(conn: sqlite3.Connection, *, pipeline_id: str,
                         target_id: int, reason: str,
                         kind: str = "Builder") -> None:
    """Mimic what pipeline.run_* does: insert a pipelines row + a
    dead_attempts row pointing at it. dead_attempts.pipeline_id has a
    FK to pipelines.id so the parent row must exist."""
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, "
        "status, outcome, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pipeline_id, kind, str(target_id), "Goal", "failed", "failed",
         db.now(), db.now()),
    )
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id, "
        "failure_reason, failure_detail, ts) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (target_id, "Goal", pipeline_id, reason, "", db.now()),
    )
    conn.commit()


def test_cascade_builder_spawn_fast_fail_skips_increment(
    conn: sqlite3.Connection,
) -> None:
    """The whole point of F46: a Builder spawn_fast_fail must NOT
    increment the goal's attempts counter. Otherwise three 2-second
    rc=1 bursts torch the cap and shelve a salvageable goal."""
    gid = _seed_goal(conn)
    pid = "fast-fail-pid"
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="spawn_fast_fail")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 0
    assert row["status"] == "open"


def test_cascade_backward_spawn_fast_fail_skips_increment(
    conn: sqlite3.Connection,
) -> None:
    """Same skip applies to Backward. The 2026-05-02 compactness run
    burned 3 of 8 attempts on Goal 129 via 2-second Backward rc=1
    bursts before the Backward branch was even taken seriously."""
    gid = _seed_goal(conn)
    pid = "fast-fail-bwd"
    cascade_one(conn, pipeline_id=pid, kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="spawn_fast_fail")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 0


def test_cascade_normal_failure_still_increments(
    conn: sqlite3.Connection,
) -> None:
    """Defense-in-depth: failure_reason='lake_build_error' is a real
    agent failure → increment attempts as before. F46 only changes
    the spawn_fast_fail path."""
    gid = _seed_goal(conn)
    pid = "real-fail"
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="lake_build_error")
    assert db.get_goal(conn, gid)["attempts"] == 1


def test_cascade_builder_gateway_unreachable_skips_increment(
    conn: sqlite3.Connection,
) -> None:
    """SG run #14 (2026-05-11): gateway IOCP accept-loop crashed mid-run,
    every Backward dispatch raised URLError [WinError 10061] from the
    daemon's own HTTP POST, the legacy worker-exception path counted
    each as a real attempt, and the root goal shelved at SHELVE_THRESHOLD
    after 5 infra refusals. `gateway_unreachable` now joins the infra
    short-circuit set so transport-level transport refusals don't burn
    the goal's attempts cap."""
    gid = _seed_goal(conn)
    pid = "gateway-down"
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="gateway_unreachable")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 0
    assert row["status"] == "open"


def test_cascade_backward_gateway_unreachable_skips_increment(
    conn: sqlite3.Connection,
) -> None:
    """Same skip applies to Backward (the kind that actually triggered
    the SG run #14 cascade)."""
    gid = _seed_goal(conn)
    pid = "gateway-down-bwd"
    cascade_one(conn, pipeline_id=pid, kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="gateway_unreachable")
    assert db.get_goal(conn, gid)["attempts"] == 0


# ---------------------------------------------------------------------
# _classify_worker_exception — transport-error classifier
# ---------------------------------------------------------------------

def test_classify_worker_exception_urlerror_is_gateway_unreachable() -> None:
    """urllib.error.URLError is the most common shape — the daemon's
    urllib.request.urlopen() raises it for any TCP-layer failure
    talking to the gateway HTTP endpoint."""
    import urllib.error
    from Tooling.core.dispatcher import _classify_worker_exception
    exc = urllib.error.URLError("connection refused")
    assert _classify_worker_exception(exc) == "gateway_unreachable"


def test_a_5xx_is_the_gateway_talking_not_the_gateway_missing() -> None:
    """`HTTPError` is a SUBCLASS of `URLError`, and that inheritance
    cost a night's run (2026-08-13).

    A gateway holding a killed daemon's leaked slots answers
    /register with 500 "no free worker slot — pool exhausted". Filed
    as `gateway_unreachable`, eight of those trip the
    consecutive-unreachable breaker and exit the daemon — a process
    that was up, healthy, and telling us exactly what was wrong. The
    HTTPError branch must therefore come FIRST; if anyone ever reorders
    them, this test is the thing that notices."""
    import io
    import urllib.error
    from Tooling.core.dispatcher import _classify_worker_exception
    exc = urllib.error.HTTPError(
        "http://127.0.0.1:8765/register", 500, "Internal Server Error",
        {}, io.BytesIO(b'{"error": "no free worker slot"}'))
    assert _classify_worker_exception(exc) == "verify_infra"


def test_a_named_gateway_refusal_classifies_the_same_way() -> None:
    """The typed refusal the register client now raises must land on
    the same reason as the raw HTTPError it replaces — otherwise
    reading the response body would have quietly changed the failure
    accounting."""
    from Tooling.core.dispatcher import _classify_worker_exception
    from Tooling.lsp.lifecycle import GatewayRefused
    exc = GatewayRefused(500, "no free worker slot — pool exhausted",
                         endpoint="/register")
    assert _classify_worker_exception(exc) == "verify_infra"


def test_gateway_refusal_does_not_feed_the_daemon_death_breaker() -> None:
    """The point of the reason, not just its spelling: whatever
    `verify_infra` is called, it must not be the reason the breaker
    counts. `failures.py` drew this line for the verify path; the
    dispatcher's classifier now shares it."""
    from Tooling.state.failures import REGISTRY
    # Same no-attempts++ semantics as the unreachable case...
    assert REGISTRY["verify_infra"].origin == "provider_infra"
    assert REGISTRY["verify_infra"].cooldown_scope == "target"
    # ...but a DIFFERENT reason string, which is the whole point: the
    # breaker counts `gateway_unreachable`, and only that.
    assert "verify_infra" in REGISTRY and "gateway_unreachable" in REGISTRY
    # agent_visible=False: a slot shortage is not a lesson about Lean.
    assert REGISTRY["verify_infra"].agent_visible is False


def test_every_reason_the_classifier_can_return_earns_a_cooldown() -> None:
    """A classified worker exception must cool its target, or the
    dispatcher re-fires the same full spawn on the very next tick.

    The worker-exception path used to name its cooling reasons by hand
    while the normal-result path read them from the registry. That was
    survivable only while the classifier returned exactly the two
    reasons the hand-list happened to contain — a coincidence, not an
    invariant. Teaching the classifier a third (`verify_infra`,
    2026-08-13) would have traded a daemon that exits in ~13 minutes
    for one that hot-loops spawns with no back-off at all.

    Read out of the AST rather than by calling with sample exceptions:
    the failure mode is a NEW return value nobody wrote a sample for."""
    import ast
    import inspect
    import textwrap
    from Tooling.core import dispatcher
    from Tooling.state.failures import TARGET_COOLDOWN_REASONS
    tree = ast.parse(textwrap.dedent(
        inspect.getsource(dispatcher._classify_worker_exception)))
    reasons = {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        and node.value.value  # "" is the unclassified fall-through
    }
    assert reasons, "could not read the classifier's return values"
    assert not sorted(r for r in reasons
                      if r not in TARGET_COOLDOWN_REASONS), (
        f"these reasons are returned by _classify_worker_exception but "
        f"declare no target cooldown in failures.py: "
        f"{sorted(reasons - TARGET_COOLDOWN_REASONS)}")


def test_classify_worker_exception_oserror_econnrefused() -> None:
    """OSError with ECONNREFUSED errno also maps (cross-platform)."""
    import errno
    from Tooling.core.dispatcher import _classify_worker_exception
    exc = OSError(errno.ECONNREFUSED, "Connection refused")
    assert _classify_worker_exception(exc) == "gateway_unreachable"


@pytest.mark.skipif(sys.platform != "win32",
                    reason="the OSError winerror slot is only populated on "
                           "Windows CPython builds")
def test_classify_worker_exception_oserror_winerror_10061() -> None:
    """Windows wraps connection-refused as WinError 10061 — the
    actual exception observed in SG run #14 was
    `<urlopen error [WinError 10061] ...>`. Test the winerror attr
    path directly with OSError carrying winerror=10061."""
    from Tooling.core.dispatcher import _classify_worker_exception
    # OSError on Windows with winerror set (and errno often unset)
    exc = OSError(0, "actively refused", None, 10061)
    assert _classify_worker_exception(exc) == "gateway_unreachable"


@pytest.mark.skipif(sys.platform != "win32",
                    reason="the OSError winerror slot is only populated on "
                           "Windows CPython builds")
def test_classify_worker_exception_oserror_winerror_64() -> None:
    """WinError 64 = ERROR_NETNAME_DELETED, the actual asyncio crash
    cause inside the gateway. Also classify as gateway_unreachable so
    the daemon side handles it consistently."""
    from Tooling.core.dispatcher import _classify_worker_exception
    exc = OSError(0, "network name no longer available", None, 64)
    assert _classify_worker_exception(exc) == "gateway_unreachable"


def test_classify_worker_exception_message_fallback() -> None:
    """Fallback for wrapped/chained exceptions whose outer type isn't
    URLError/OSError but whose message still mentions the WinError
    code (e.g. RuntimeError wrapping the URLError text)."""
    from Tooling.core.dispatcher import _classify_worker_exception
    exc = RuntimeError("worker bombed: [WinError 10061] refused")
    assert _classify_worker_exception(exc) == "gateway_unreachable"


def test_classify_worker_exception_real_bug_returns_empty() -> None:
    """Non-transport exceptions (genuine pipeline bug, attribute error,
    etc.) return empty string so cascade_one falls through to the
    normal attempts++ path — we still want to advance toward shelve
    when a real bug breaks repeatedly."""
    from Tooling.core.dispatcher import _classify_worker_exception
    assert _classify_worker_exception(
        AttributeError("missing field")) == ""
    assert _classify_worker_exception(
        KeyError("unknown")) == ""
    assert _classify_worker_exception(
        ValueError("bad input")) == ""


def test_classify_worker_exception_timeout_is_transient_timeout() -> None:
    """Pipeline-side LSP RPC timeouts (lsp_client.py:169 raises
    TimeoutError when `$/lean/rpc/call` exceeds budget) are infra-class
    failures: no attempts++, cooldown + retry. But they MUST NOT count
    toward the gateway-death circuit breaker — under healthy
    concurrency (miniF2F pilot: 5 simultaneous Builders > 3 worker
    slots), timeouts cluster on slot-wait and would prematurely kill
    the daemon if classified as gateway_unreachable.

    Reproducer: miniF2F pilot 2026-05-11 — Goal 435 + 439 timed out on
    slot acquire during first wave; both eventually re-dispatched and
    proved. Without this classification the attempts++ would have
    counted as real failures toward SHELVE_THRESHOLD."""
    from Tooling.core.dispatcher import _classify_worker_exception
    assert _classify_worker_exception(
        TimeoutError("LSP request '$/lean/rpc/call' timed out")
    ) == "transient_timeout"
    # Generic TimeoutError still routes through the same bucket
    assert _classify_worker_exception(TimeoutError()) == "transient_timeout"


def test_classify_worker_exception_oserror_etimedout_still_gateway() -> None:
    """OSError with errno=ETIMEDOUT is socket-level timeout from
    urllib (transport actually unreachable, peer didn't ACK).
    Keep classifying as gateway_unreachable (existing behavior) —
    distinct from the application-layer TimeoutError above."""
    import errno
    from Tooling.core.dispatcher import _classify_worker_exception
    exc = OSError(errno.ETIMEDOUT, "Connection timed out")
    assert _classify_worker_exception(exc) == "gateway_unreachable"


# ---------------------------------------------------------------------
# 4. bfs_refill respects cooldown_until
# ---------------------------------------------------------------------

def test_bfs_refill_skips_cooled_target(
    conn: sqlite3.Connection,
) -> None:
    """When (target,kind) cooldown_until is in the future, bfs_refill
    does not enqueue. Once the cooldown expires it resumes normally."""
    import time
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    cooldown_until = {(str(gid), "Formalizer"): time.time() + 60.0}
    bfs_refill(conn, set(), cooldown_until)
    assert db.queue_size(conn) == 0


def test_bfs_refill_dispatches_when_cooldown_expired(
    conn: sqlite3.Connection,
) -> None:
    import time
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    # Cooldown already in the past — should NOT block. The key must carry
    # the kind bfs_refill actually dispatches (v33: always "Formalizer");
    # a retired kind here never matches, and the test passes even if the
    # cooldown check is deleted outright.
    cooldown_until = {(str(gid), "Formalizer"): time.time() - 1.0}
    bfs_refill(conn, set(), cooldown_until)
    assert db.queue_size(conn) == 1


def test_bfs_refill_no_cooldown_dict_back_compat(
    conn: sqlite3.Connection,
) -> None:
    """Existing tests (and any external callers) still pass running
    only — cooldown_until=None must mean "no cooldown anywhere"."""
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    bfs_refill(conn, set())  # no cooldown arg
    assert db.queue_size(conn) == 1


# ---------------------------------------------------------------------
# 4. system_killed — the OS killed the spawn, not the agent (2026-08-08)
# ---------------------------------------------------------------------

def test_spawn_failure_classifies_ntstatus_as_system_killed(
    tmp_path: Path,
) -> None:
    """The three NTSTATUS codes a dying workstation actually handed us
    (fail-fast, DLL-init, debugger-terminate) must classify as
    provider infra — burning attempts on them shoved five healthy
    goals into strategist review while the machine was thrashing."""
    from Tooling.state import failures
    for rc in (0xC0000409, 0xC0000142, 0x40010004):
        reason, detail = _pipeline._spawn_failure(
            rc=rc, attempts_dir=tmp_path, spawn_dur=120.0)
        assert reason == "system_killed", hex(rc)
        assert f"0x{rc:08X}" in detail
        assert failures.is_infra(reason)


def test_spawn_failure_ntstatus_beats_fast_fail_window(
    tmp_path: Path,
) -> None:
    """A system kill inside the 10s window is still `system_killed` —
    the honest label, same no-burn semantics."""
    reason, _ = _pipeline._spawn_failure(
        rc=0xC0000005, attempts_dir=tmp_path, spawn_dur=1.0)
    assert reason == "system_killed"


def test_spawn_failure_classifies_bun_panic_as_system_killed(
    tmp_path: Path,
) -> None:
    """claude.exe is a Bun standalone; a runtime panic exits with a
    SMALL rc (observed: 3) but stamps its crash banner on stderr.
    Same class: the CLI died, the agent chose nothing."""
    (tmp_path / "_spawn.stderr").write_text(
        "rc=3\n" + "=" * 60 + "\n"
        "Bun v1.4.0 (eb835313a) Windows x64 (baseline)\n"
        "Windows v10.26200\nCPU: sse42 avx avx2\n"
        'Args: "claude" "--model" "claude-sonnet-5" "-p" "..."\n'
        "Features: fetch jsc spawn(3) claude_code\n",
        encoding="utf-8")
    reason, detail = _pipeline._spawn_failure(
        rc=3, attempts_dir=tmp_path, spawn_dur=45.0)
    assert reason == "system_killed"
    assert "runtime crashed" in detail


def test_spawn_failure_small_rc_without_banner_is_unclassified(
    tmp_path: Path,
) -> None:
    """rc=3 with ordinary agent stderr is NOT a runtime crash — the
    banner, not the code, is the discriminator. It lands in the
    unclassified bucket rather than `system_killed`: we can say what it
    is NOT, which is not the same as knowing what it is."""
    (tmp_path / "_spawn.stderr").write_text(
        "rc=3\nsome ordinary tool error output", encoding="utf-8")
    reason, _ = _pipeline._spawn_failure(
        rc=3, attempts_dir=tmp_path, spawn_dur=45.0)
    assert reason == "unclassified_spawn_failure"


def test_worker_exception_memory_exhaustion_is_system_killed() -> None:
    """WinError 1455 (pagefile / commitment limit) and MemoryError are
    the machine dying, not the goal failing — ten of them burned ten
    attempts across five goals on 2026-08-08 via the "" default."""
    from Tooling.core.dispatcher import _classify_worker_exception
    e = OSError("pagefile too small")
    e.winerror = 1455
    assert _classify_worker_exception(e) == "system_killed"
    e8 = OSError("not enough memory")
    e8.winerror = 8
    assert _classify_worker_exception(e8) == "system_killed"
    assert _classify_worker_exception(MemoryError()) == "system_killed"
    # Transport classification is untouched.
    e2 = OSError("refused")
    e2.winerror = 10061
    assert _classify_worker_exception(e2) == "gateway_unreachable"


# ---------------------------------------------------------------------
# 5. Unknown causes do not charge the goal (owner ruling, 2026-08-08)
# ---------------------------------------------------------------------

def test_unrecognised_rc_is_unclassified_not_agent_fault(
    tmp_path: Path,
) -> None:
    """The counter answers "did the worker get a fair chance and fail?".
    An rc nothing recognises cannot answer that, so it must not be
    charged. Every death mode this project has met — NTSTATUS exits, a
    Bun panic, a gateway 500, a pagefile exhaustion — first arrived as
    an unrecognised rc and was silently billed to the agent until an
    audit found it."""
    from Tooling.state import failures
    reason, detail = _pipeline._spawn_failure(
        rc=42, attempts_dir=tmp_path, spawn_dur=300.0)
    assert reason == "unclassified_spawn_failure"
    assert failures.is_infra(reason)          # ⇒ no attempts++
    assert reason in failures.PROVIDER_INFRA_REASONS   # the skip reads this
    # Traceable: the price of not guessing is that the record must carry
    # enough to classify it later.
    assert "rc=42" in detail and "300s" in detail


def test_unclassified_is_not_shown_to_the_agent(tmp_path: Path) -> None:
    """An unexplained mechanical fault teaches the agent nothing, and
    projecting it invites a mathematical narrative for a machine fault
    (a gateway 500 once reached a worker as "your Lean failed to
    build")."""
    from Tooling.state import failures
    assert "unclassified_spawn_failure" in failures.NON_AGENT_REASONS
    assert "unclassified_spawn_failure" not in failures.DEATH_NOTE_REASONS


def test_a_fair_chance_consumed_still_counts(tmp_path: Path) -> None:
    """The other half of the rule: a spawn that HELD the full budget and
    delivered nothing did get its chance. Timeouts keep agent traits —
    narrowing the entrance must not empty it, or a goal that can never
    be formalized would never reach the Strategist."""
    from Tooling.state import failures
    reason, _ = _pipeline._spawn_failure(
        rc=124, attempts_dir=tmp_path, spawn_dur=960.0)
    assert reason == "agent_timeout"
    assert not failures.is_infra(reason)      # ⇒ attempts++ as before


def test_unclassified_breaker_limit_is_tighter_than_fast_fail() -> None:
    """Repetition escalates to the OPERATOR, not the Strategist: a
    framework fault is not something re-planning fixes, and handing one
    to the Strategist only gets it rewritten as mathematics. The limit
    sits below the fast-fail one because a fast-fail has a known shape
    and a known remedy; "we cannot name this" repeating does not."""
    from Tooling.core import dispatcher
    assert (dispatcher.CONSEC_UNCLASSIFIED_LIMIT
            < dispatcher.CONSEC_SPAWN_FAIL_LIMIT)
    assert "consec_unclassified" in dispatcher.SchedulerState().__dict__
