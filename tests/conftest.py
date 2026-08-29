"""Pytest fixtures shared across test modules."""
from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import urllib.parse
from pathlib import Path

import pytest

from Tooling.state import db


def pytest_collection_modifyitems(config, items):
    """Drop `real_lake`- and `slow`-marked tests from the default run.

    They spawn a live lake/lean toolchain — slow (seconds to minutes) and only
    runnable where Mathlib is built (the dev workstation). CI runners have no
    Lean, so they cannot run there either; in the routine `pytest` they were
    pure cost — a cold spawn that flakes on timeout, or a `skipif` skip. Keep
    the default run fast and all-green by not collecting them at all (silent —
    no skip/deselect line). Opt in where lake is present with
    `ASTERISM_REAL_LAKE=1 pytest`, or `pytest -m real_lake`."""
    expr = config.option.markexpr or ""
    drop = set()
    if not (os.environ.get("ASTERISM_REAL_LAKE") or "real_lake" in expr):
        drop.add("real_lake")
    # `slow` (2026-08-29, owner: suite length is a cost): whole-corpus
    # scans and other minute-scale checks run on opt-in — ASTERISM_SLOW_TESTS=1
    # or `pytest -m slow` — not on every commit.
    if not (os.environ.get("ASTERISM_SLOW_TESTS") or "slow" in expr):
        drop.add("slow")
    if drop:
        items[:] = [it for it in items if not (drop & set(it.keywords))]


# ---------------------------------------------------------------------
# Side-effect fence (task #6) — "unit tests never spawn the toolchain or
# touch the real network" was fixture DISCIPLINE until 2026-07-05, and it
# failed silently once: an inconsistent import let `_presearch` reach an
# unstubbed `agent.spawn_llm`, a REAL claude subprocess idled 270s per
# test, and the suite ran 20min instead of 65s — green the whole time
# (fixed twice as convention: import unification + env kill switch;
# 1488da4). The fence turns that silent degradation into an instant,
# named failure — the same discipline→mechanism upgrade as the raw-UPDATE
# ratchet and the proof_store lint.
# ---------------------------------------------------------------------

# Executable basenames whose spawn means "the toolchain escaped a stub".
# git / python / py-spy etc. stay allowed — the fence targets the
# expensive, quota-burning, minutes-long escapes, not all subprocesses.
_FENCED_EXES = frozenset({
    "claude", "claude.exe", "claude.cmd",
    # agy is the second quota-burning backend and belonged here from the
    # day it landed: it is now reachable from the serve layer too (the
    # console explainer resolves its provider through the registry), and
    # an escaped agy spawn costs the same subscription an escaped claude
    # spawn does. Its two legitimate probes are `free_cli_probe`-marked
    # and pass the argv check below (`--version`, the drift-guard tail).
    "agy", "agy.exe", "agy.cmd",
    # codex is the third quota-burning backend (seated 2026-08-13). Its
    # one legitimate probe is `free_cli_probe`-marked and passes the
    # argv check below (`--version`, the drift-guard tail).
    "codex", "codex.exe", "codex.cmd",
    "lake", "lake.exe", "lean", "lean.exe",
    "lean-asterism-server", "lean-asterism-server.exe",
    "loogle", "loogle.exe",
})

_REAL_POPEN = subprocess.Popen
_REAL_CONNECT = socket.socket.connect


@pytest.fixture(autouse=True)
def _no_provider_drift_probe(monkeypatch: pytest.MonkeyPatch):
    """Keep the daemon's provider drift guard from shelling out.

    `cmd_run` starts it in a BACKGROUND thread, so a test that exercises
    the run path (test_cli_reset_status, test_cli_logs, …) would fire two
    real CLI cold starts per test — and, because the thread outlives the
    fence's monkeypatch scope, trip the side-effect fence from a thread
    whose failure pytest can only report as a warning. Tests that mean to
    probe (`test_provider_drift_guard.py`) delete the variable
    themselves."""
    monkeypatch.setenv("ASTERISM_SKIP_PROVIDER_DRIFT_CHECK", "1")
    yield


@pytest.fixture(autouse=True)
def _reset_spawn_shutdown_state():
    """Clear the provider's module-level shutdown Event after every test.

    `claude_cli.request_shutdown()` sets a process-wide Event and there
    is no production path that clears it — the caller hard-exits. Tests
    stub that exit, so any test reaching the FATAL path (today:
    `test_cli_logs.py::test_cmd_run_logs_traceback_on_crash`) leaves the
    flag set, and every later `ClaudeCliProvider.spawn` in the process
    returns SHUTDOWN before invoking anything.

    The suite was green only by luck of alphabetical ordering: a file
    between the setter and the victims (`test_e2e_dispatcher.py`) calls
    the reset for its own reasons. Renaming a file, or running a subset,
    turns 33 unrelated tests red with an error that names none of the
    causes. One autouse teardown makes order irrelevant.
    """
    yield
    try:
        from Tooling.llm import claude_cli
        claude_cli._reset_shutdown_for_tests()
    except Exception:  # noqa: BLE001 — teardown must never mask a failure
        pass


@pytest.fixture(autouse=True)
def _side_effect_fence(request, monkeypatch: pytest.MonkeyPatch):
    """Fail fast (with the offending test named by pytest itself) when a
    non-`real_lake` test tries to spawn the Lean/LLM toolchain or open a
    non-loopback network connection.

    Loopback connects stay ALLOWED: asyncio event loops create localhost
    socketpairs internally (the gateway endpoint tests would trip a
    blanket ban), and in a unit-test run nothing listens on the gateway
    port anyway — an escaped localhost call fails as ECONNREFUSED, which
    the transient-retry paths already surface. The expensive silent
    escapes (claude/lake spawns, loogle web calls) are what this fence
    exists to catch."""
    if "real_lake" in request.keywords:
        yield
        return

    def _exe_name(args) -> str:
        import re as _re
        if isinstance(args, (str, bytes)):
            first = args.split()[0] if args else ""
        elif isinstance(args, (list, tuple)) and args:
            first = args[0]
        else:
            first = ""
        if isinstance(first, bytes):
            first = first.decode(errors="replace")
        # Split on BOTH separators: POSIX basename doesn't cut a
        # Windows-style path (CI ubuntu leg would let `C:\...\claude.exe`
        # through to a real — failing — Popen).
        return _re.split(r"[\\/]", str(first))[-1].lower()

    # A CLASS, not a function: modules first-imported while the fence
    # is up may evaluate `subprocess.Popen[bytes]` annotations at class
    # definition time (mcp's win32 utilities do) — a plain function
    # isn't subscriptable and the import exploded, but only in isolated
    # runs where no earlier collection had cached the import
    # (test_gateway_lifecycle.py alone, 2026-07-09).
    # A narrow hole for the provider-capability probes (2026-08-09).
    # The fence's premise is "a claude.exe spawn here means a stub was
    # bypassed and something expensive / quota-burning escaped". The
    # capability layer's probes are the exception that proves it: they
    # are answered LOCALLY (`--version`; `--resume <nonexistent uuid>`;
    # `--model <invalid slug>`), cost no tokens, and are the only way to
    # verify that the string-match detectors still match the CLI's own
    # output. `real_lake` is the wrong hatch — it is OFF by default, so
    # marking them would silently stop running the one check that
    # notices a vendor CLI moved under us.
    #
    # The hole stays honest by checking the ARGV, not just the marker: a
    # `free_cli_probe` test that accidentally launches a real agent
    # spawn still fails, because `-p <prompt>` alone is not on the list.
    free_probe = "free_cli_probe" in request.keywords

    def _is_free_probe(args) -> bool:
        if not free_probe or not isinstance(args, (list, tuple)):
            return False
        tail = tuple(str(x) for x in args[1:])
        if tail[:1] == ("--version",):
            return True
        try:
            from Tooling.llm.drift_guard import PROBES
        except Exception:  # noqa: BLE001
            return False
        return any(tail == p.argv_tail for p in PROBES.values())

    class _FencedPopen(_REAL_POPEN):
        def __init__(self, args, *a, **kw):
            name = _exe_name(args)
            if name in _FENCED_EXES and not _is_free_probe(args):
                pytest.fail(
                    f"side-effect fence: this test tried to spawn {name!r} "
                    f"(argv[0]="
                    f"{args if isinstance(args, str) else args[0]!r}). "
                    "A toolchain/LLM stub was bypassed — stub "
                    "`agent.spawn_llm` / `gateway_lifecycle.verify_file` "
                    "(or the layer this call escaped from), or mark the "
                    "test `real_lake`.",
                    pytrace=True)
            super().__init__(args, *a, **kw)

    def _fenced_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in (
                "127.0.0.1", "localhost", "::1"):
            pytest.fail(
                f"side-effect fence: this test tried a real network "
                f"connection to {address!r}. Stub the HTTP/web layer "
                "(urlopen / loogle), or mark the test `real_lake`.",
                pytrace=True)
        return _REAL_CONNECT(self, address)

    monkeypatch.setattr(subprocess, "Popen", _FencedPopen)
    monkeypatch.setattr(socket.socket, "connect", _fenced_connect)
    yield


# ---------------------------------------------------------------------
# Live-data fence (task #180) — the side-effect fence above guards the
# OUTSIDE world (spawns, network). This one guards ours.
#
# `db.DB_PATH` is the RELATIVE `Path("asterism.db")`, so every default
# `db.connect()` resolves against whatever CWD the test happens to run
# under — and pytest is normally launched from the repo root, where the
# operator's live run DB sits. A fixture that forgets
# `monkeypatch.chdir(tmp_path)` therefore opens the real one, and
# `connect()` does not merely read it: it auto-migrates a behind-schema
# DB (a write) before the test's own DELETEs and UPDATEs land.
#
# That file is the one artifact in the tree that cannot be regenerated.
# Source is in git, proofs are on disk, but the DB *is* the run — the
# current tree cost tens of hours of subscription quota, and re-running
# it does not reproduce it, it grows a different tree. `.asterism/` is
# protected on the same grounds: those backups are the recovery path,
# not a spare copy.
#
# Unlike the side-effect fence, this one applies to `real_lake` tests
# too. Needing a live toolchain is not a reason to need live run state.
# ---------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REAL_SQLITE_CONNECT = sqlite3.connect

# Exact files, then whole subtrees. Both are compared against a RESOLVED
# path, so a tmp_path copy of the DB (the legal way to test against real
# data) never matches.
_PROTECTED_DB_FILES = (_REPO_ROOT / "asterism.db",)
_PROTECTED_DB_DIRS = (
    _REPO_ROOT / ".asterism",             # backups + daemon runtime state
    Path.home() / ".gemini",              # agy's conversations/*.db
)


def _sqlite_target_path(database) -> "Path | None":
    """Resolve what a `sqlite3.connect` first argument names on disk.

    Returns None for the forms that touch no operator file: `:memory:`,
    the anonymous temp DB (`""`), and unparseable arguments."""
    if isinstance(database, bytes):
        database = database.decode(errors="replace")
    elif isinstance(database, os.PathLike):
        database = os.fspath(database)
    if not isinstance(database, str) or not database or database == ":memory:":
        return None
    if database.startswith("file:"):
        # URI form — `db.connect_readonly` builds one. Strip scheme,
        # authority and query before touching the filesystem; a read-only
        # open of live state is still a test-isolation defect (the test
        # then depends on whatever the daemon last wrote).
        rest = database[len("file:"):].split("?", 1)[0]
        if rest.startswith("//"):
            rest = rest[2:].split("/", 1)[-1]
        if not rest or rest == ":memory:":
            return None
        database = urllib.parse.unquote(rest)
    try:
        return Path(database).resolve()
    except (OSError, ValueError):
        return None


def _protected_db_reason(target: Path) -> str:
    for f in _PROTECTED_DB_FILES:
        if target == f:
            return f"{f} is the operator's LIVE run database"
    for d in _PROTECTED_DB_DIRS:
        try:
            target.relative_to(d)
        except ValueError:
            continue
        return f"{target} lives under {d}, which holds live operator state"
    return ""


@pytest.fixture(autouse=True)
def _live_data_fence(request, monkeypatch: pytest.MonkeyPatch):
    """Fail fast when a test opens the operator's real sqlite state."""
    if "live_db" in request.keywords:
        yield
        return

    def _fenced_sqlite_connect(database, *a, **kw):
        target = _sqlite_target_path(database)
        if target is not None:
            why = _protected_db_reason(target)
            if why:
                pytest.fail(
                    f"live-data fence: this test opened {str(target)!r} — "
                    f"{why}, not test state.\n"
                    "Almost always a missing `monkeypatch.chdir(tmp_path)`: "
                    "`db.DB_PATH` is relative, so the default `db.connect()` "
                    "follows the CWD straight to the real file. Fix by "
                    "chdir-ing into `tmp_path` first, passing an explicit "
                    "path under `tmp_path`, or using the in-memory `conn` "
                    "fixture. Mark the test `live_db` only if reading the "
                    "operator's own run is the point of the test.",
                    pytrace=True)
        return _REAL_SQLITE_CONNECT(database, *a, **kw)

    monkeypatch.setattr(sqlite3, "connect", _fenced_sqlite_connect)
    yield


@pytest.fixture(autouse=True)
def _stub_cold_lake_by_default(request, monkeypatch: pytest.MonkeyPatch):
    """Stub the two COLD-lake seams (`_lake.lake_build_modules` olean
    pre-flight, `lake_probe.run_lean_source` one-shot probes) the way the
    warm-gateway seams already are. The side-effect fence's first live
    catch (2026-07-05) was exactly this class: a backward-commit test's
    dedupe pre-flight ran a REAL `lake build` every run — silently slow
    on the workstation, silently FileNotFoundError-swallowed on CI.
    Tests exercising cold-lake behavior override locally (their
    monkeypatch applies after this autouse one and wins)."""
    if "real_lake" in request.keywords:
        return
    from Tooling.knowledge import lemma_lookup
    from Tooling.pipeline import _lake
    from Tooling.quality import dedupe as _dd
    from Tooling.quality import lake_probe
    # Third member of the class, caught by the fence ON CI (2026-07-05):
    # compile_context #checks lemma names mined from dead attempts via
    # lookup_batch — a cold `lake env lean` whose on-disk JSON cache made
    # it a silent no-op locally and a real spawn on cache-less CI.
    monkeypatch.setattr(lemma_lookup, "lookup_batch",
                        lambda names, workspace, **kw: {})
    monkeypatch.setattr(_lake, "lake_build_modules",
                        lambda workspace, modules: (True, ""))
    # Clean "probe says no" verdict (rc=1, no output): dedupe defeq → not
    # equal → no drop; conservative in every consumer's failure direction.
    monkeypatch.setattr(
        lake_probe, "run_lean_source",
        lambda workspace, content, **kw: lake_probe.LeanRun(1, "", False))
    # The apply probe shells `lake env lean` directly (not via
    # run_lean_source): stub to all-no-hit (dedupe's fail-open shape).
    monkeypatch.setattr(
        _dd, "_batch_provable_via_apply",
        lambda workspace, problem, pairs: [False] * len(pairs))


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
def _strict_transitions_by_default(monkeypatch: pytest.MonkeyPatch):
    """The transition registry / proved-receipt / main-thread checks run
    STRICT across the whole suite, so CI actually proves what
    transitions.py's module docstring claims it proves: every exercised
    code path stays inside the declared edge set AND every proved-flip
    carries a ProvedReceipt. (Before 2026-07-04 strict was opt-in per
    test and the docstring's 'Tests / CI set …=1' was aspirational.)
    Tests that exercise LENIENT production behavior delenv locally."""
    monkeypatch.setenv("ASTERISM_STRICT_TRANSITIONS", "1")


@pytest.fixture(autouse=True)
def _skip_lean_contract_gate(monkeypatch: pytest.MonkeyPatch):
    """The daemon-startup framework⇄Lean contract gate (task #12) would run
    its real-toolchain contracts against this conftest's verify stubs and
    fail honestly (stubbed axiom sets are empty) — wedging every e2e that
    drives dispatcher.run(). Unit tests exercise scheduling, not the
    toolchain; the gate has its own Lean-free unit tests
    (test_lean_contracts.py) + real_lake wrappers for the real thing."""
    from Tooling.quality import lean_contracts
    monkeypatch.setattr(lean_contracts, "check_on_startup", lambda ws: True)


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
def _disable_presearch_by_default(monkeypatch: pytest.MonkeyPatch):
    """target-1 pre-search (`_presearch.ensure_presearch`) spawns a per-node
    candidate-lemma agent BEFORE the prover. In unit tests it is irrelevant
    noise, and worse: its spawn reference (`from ..agent import runtime as
    agent`) escaped the pipeline tests' `monkeypatch.setattr(agent,
    "spawn_llm", …)` stub, so it spawned a REAL claude subprocess that blocked
    on subprocess.wait for the full timeout ×3 retry stages — 270s on ONE test,
    ~18 of the 20-min suite. (The import is now unified so it IS stubbable, but
    a running pre-search would still add an extra spawn to exact-count
    assertions.) Disable by default — same rationale as reflection above.
    `test_presearch` tests `_verify`/`presearch_path` directly, not
    `ensure_presearch`, so it is unaffected."""
    monkeypatch.setenv("ASTERISM_PRESEARCH_ENABLED", "false")


@pytest.fixture(autouse=True)
def _stub_gateway_calls_by_default(monkeypatch: pytest.MonkeyPatch,
                                   request: pytest.FixtureRequest):
    """`pipeline._write_mcp_config` POSTs to the long-living gateway
    (`Tooling/lsp_gateway.py`) at /register to obtain a session token,
    and POSTs /release on retry overwrite. Unit tests don't run a real
    gateway, so we stub urllib.request.urlopen to return a fake
    session token + 200 OK release. Production callers (dispatcher
    starts the gateway via gateway_lifecycle.start_gateway) hit the
    real HTTP endpoint.

    `real_lake`-marked tests want the REAL gateway (they opt into a
    live toolchain), so skip stubbing for them entirely."""
    if "real_lake" in request.keywords:
        return
    import io
    import urllib.request

    class _FakeResp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self._body

    def _fake_urlopen(req, timeout=None):
        # Fake responses for the endpoints framework code hits.
        url = getattr(req, "full_url", str(req))
        if url.endswith("/register"):
            return _FakeResp(b'{"session_token": "test-stub-token"}')
        if "/release/" in url:
            return _FakeResp(b'{"ok": true}')
        if url.endswith("/verify"):
            # Verify-unification: framework's gateway-side verify
            # entry point. Default stub passes — tests that exercise
            # the failure path must override the higher-level
            # `gateway_lifecycle.verify_file` directly. (HTTP-level
            # stub is kept as belt-and-braces in case a test forgets
            # to patch the function-level call.)
            return _FakeResp(
                b'{"ok": true, "diagnostic_count": 0, "diagnostics": [],'
                b' "olean_written": true, "olean_path": null,'
                b' "axioms": null, "axiom_error": null}'
            )
        # Anything else (e.g. /health from gateway_lifecycle.start_gateway)
        # — raise URLError so tests don't accidentally see a "fake healthy"
        # gateway. End-to-end tests that need start_gateway to work must
        # stub it directly.
        raise urllib.error.URLError("(test) no real gateway running")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)


@pytest.fixture(autouse=True)
def _stub_axiom_probe_by_default(monkeypatch: pytest.MonkeyPatch,
                                 request: pytest.FixtureRequest):
    """Builder / verify_strategy / `_try_promote_sorry_free` run a real
    `#print axioms <name>` probe at promote time. After the verify-
    unification migration this goes through `gateway_lifecycle.verify_file`,
    which needs the gateway running + a real Lean toolchain. Unit tests
    don't provide that, so stub two layers:

      1. `_axiom.axiom_probe(_file)` — direct callers (Builder Phase 1
         hint, library.promote, etc.) bypass the gateway entirely.
      2. `gateway_lifecycle.verify_file` — verify_strategy / Builder
         Phase 2 verify go through this directly. Stub returns the
         shape `verify_file` produces on a clean elaborate.

    Tests exercising axiom-violation rejection
    (`tests/test_axiom_invariant.py`) override locally.

    `real_lake`-marked tests want the REAL probe / verify — skip."""
    if "real_lake" in request.keywords:
        return
    def _stub_ok(*args, **kwargs):
        return True, "axioms ok: [] (test stub)"
    from Tooling.pipeline import _axiom
    from Tooling.lsp import lifecycle as _gl
    monkeypatch.setattr(_axiom, "axiom_probe_file", _stub_ok)
    monkeypatch.setattr(_axiom, "axiom_probe", _stub_ok)

    def _stub_verify_file(target_path, *, write_olean=True,
                          axioms_for=None, constants_for=None,
                          decl_info=False,
                          timeout=120.0, workspace=None,
                          _retry_delays=None):
        return {
            "ok": True,
            "diagnostic_count": 0,
            "diagnostics": [],
            "olean_written": write_olean,
            "olean_path": str(target_path),
            "axioms": [] if axioms_for else None,
            "axiom_error": None,
            "pending_anchors": [] if constants_for else None,
            "top_kind": None,
            "top_is_prop": None,
            "top_module": None,
            "closure_error": None,
            # declInfo oracle: the clean-elaborate stub has no decl facts;
            # consumer tests that need them override verify_file locally.
            "decl_info": ({"commands": [], "decls": []} if decl_info
                          else None),
            "decl_info_error": None,
        }
    monkeypatch.setattr(_gl, "verify_file", _stub_verify_file)

    # The own-slot probe path (`_axiom.axiom_gate` / `verify_on_own_slot` when
    # the pipeline holds a session token — which unit tests ALWAYS do, via the
    # /register urlopen stub above). DELEGATE to whatever verify_file is
    # currently stubbed to (resolved at CALL time), so a test that overrides
    # verify_file — to fail a build, inject sorryAx, etc. — also controls the
    # own-slot gate path without having to stub both. CAVEAT: the delegation
    # passes CONTENT where verify_file expects a path — a test stub that
    # discriminates by target_path will misfire on the own-slot path; such
    # tests must stub verify_in_session themselves and discriminate by
    # content (see test_run_forward_dedupe_alias_build_fails_falls_back_…).
    def _stub_verify_in_session(token, content, *, write_olean=False,
                                axioms_for=None, decl_info=False,
                                timeout=240.0,
                                workspace=None, _retry_delays=None):
        return _gl.verify_file(
            content, write_olean=write_olean, axioms_for=axioms_for,
            decl_info=decl_info, workspace=workspace)
    monkeypatch.setattr(_gl, "verify_in_session", _stub_verify_in_session)
