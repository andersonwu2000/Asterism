"""Phase 2 Step 6 finisher — end-to-end integration tests for
`run_strategist` + `run_forward` with mocked agent.spawn_llm.

Tests the full stage chain: context compile → spawn → parse → verify
→ commit. Mirrors test_e2e_dispatcher pattern (monkeypatch spawn_llm,
let everything else run real).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling import agent
from Tooling.pipeline import strategist, forward
from Tooling.state import db, manifest


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\nT\n", encoding="utf-8")
    (pdir / "proofs").mkdir()
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


@pytest.fixture
def mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="T")


def _insert_root(conn: sqlite3.Connection) -> int:
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean", statement="T",
        origin="root", depth=0, entry_kind="Backward",
    )


# ---------------------------------------------------------------------
# run_strategist — full chain with mocked spawn_llm
# ---------------------------------------------------------------------

def test_run_strategist_commits_noop(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strategist Noop: agent ships decision.json with kind=Noop;
    commit records audit row + bumps last_strategist_at; run returns
    failed/strategist_noop (infra-reason)."""
    _insert_root(conn)
    pipeline_id = "test-strat-1"

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({"kind": "Noop", "reason": "waiting for BFS"}),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id=pipeline_id,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "strategist_noop"
    # Audit row exists
    row = conn.execute(
        "SELECT decision_kind FROM strategist_decisions WHERE problem='p'"
    ).fetchone()
    assert row["decision_kind"] == "Noop"
    # last_strategist_at bumped by the commit
    p = conn.execute(
        "SELECT last_strategist_at FROM problems WHERE name='p'"
    ).fetchone()
    assert p["last_strategist_at"] is not None


def test_run_strategist_inject_enqueues_forward(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strategist Inject(Forward, brief=...): commit enqueues Forward
    on the problem with decision_id FK. Phase 6 schema: single brief
    per Inject decision (multi-brief lands via multi-decision)."""
    _insert_root(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({
                "kind": "Inject", "pipeline": "Forward",
                "brief": "## Need\nA contour lemma.",
            }),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=2,
        workspace=workspace, mfst=mfst, pipeline_id="test-strat-2",
    )
    assert r.outcome == "success"
    # Forward enqueued
    q = conn.execute(
        "SELECT kind, target_id, target_kind, decision_id FROM queue"
        " WHERE kind='Forward'"
    ).fetchone()
    assert q is not None
    assert q["target_id"] == "p"
    assert q["target_kind"] == "Problem"
    assert q["decision_id"] is not None


def test_run_strategist_schema_invalid_returns_infra_reason(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent drops malformed decision.json → strategist_schema_invalid."""
    _insert_root(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "decision.json").write_text(
            "not valid json",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=3,
        workspace=workspace, mfst=mfst, pipeline_id="test-strat-3",
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "strategist_schema_invalid"


def test_run_strategist_no_output(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent rc=0 but no decision.json → agent_no_output."""
    _insert_root(conn)

    def fake_spawn(**kw):
        return 0  # no file dropped
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=4,
        workspace=workspace, mfst=mfst, pipeline_id="test-strat-4",
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "agent_no_output"


def test_run_strategist_quota_exhausted_rc(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rc=126 → quota_exhausted (infra-reason; dispatcher cools the
    kind, root.attempts unchanged)."""
    _insert_root(conn)

    def fake_spawn(**kw):
        return 126
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=5,
        workspace=workspace, mfst=mfst, pipeline_id="test-strat-5",
    )
    assert r.failure_reason == "quota_exhausted"


# ---------------------------------------------------------------------
# Verify-retry — single in-pipeline retry when verify_decisions rejects
# the first decision.json. Covers the failure modes most plausibly
# fixable by re-prompting (bad slug, dead ancestor, missing brief,
# cross-decision conflicts).
# ---------------------------------------------------------------------

def test_run_strategist_verify_retry_recovers(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First attempt produces an Inject against a non-existent target
    (verify fails); retry produces a valid Noop. Run reports success."""
    _insert_root(conn)
    calls: list[dict] = []

    def fake_spawn(**kw):
        calls.append(kw)
        attempts_dir = kw["attempts_dir"]
        if len(calls) == 1:
            (attempts_dir / "decision.json").write_text(
                json.dumps({
                    "kind": "Inject", "pipeline": "Backward",
                    "target_goal_id": 9999, "brief": "stale id",
                }),
                encoding="utf-8")
        else:
            (attempts_dir / "decision.json").write_text(
                json.dumps({"kind": "Noop", "reason": "ok"}),
                encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=6,
        workspace=workspace, mfst=mfst, pipeline_id="test-strat-retry-1",
    )
    # Noop maps to strategist_noop (infra-reason) but the retry IS the
    # success path: it produced a parsable + verifiable decision.
    assert r.failure_reason == "strategist_noop"
    assert len(calls) == 2
    # Same session_id across both spawns; second was is_retry=True with
    # the first attempt's verify error in retry_context.
    assert calls[0]["session_id"] == calls[1]["session_id"]
    assert calls[0].get("is_retry", False) is False
    assert calls[1]["is_retry"] is True
    assert "9999" in calls[1]["retry_context"]


def test_run_strategist_verify_retry_both_fail(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both attempts produce verify-failing output → schema_invalid
    with both errors surfaced in failure_detail."""
    _insert_root(conn)
    calls: list[dict] = []

    def fake_spawn(**kw):
        calls.append(kw)
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({"kind": "Inject", "pipeline": "Backward",
                        "target_goal_id": 9999, "brief": "stale"}),
            encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=7,
        workspace=workspace, mfst=mfst, pipeline_id="test-strat-retry-2",
    )
    assert r.failure_reason == "strategist_schema_invalid"
    assert len(calls) == 2
    assert "verify-retry" in r.failure_detail
    assert "first-attempt" in r.failure_detail


def test_run_strategist_parse_fail_is_not_retried(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parse failure (malformed JSON) skips the retry path — session
    breakage usually doesn't recover from one more shot at the same
    prompt, so we don't burn the call."""
    _insert_root(conn)
    calls: list[dict] = []

    def fake_spawn(**kw):
        calls.append(kw)
        (kw["attempts_dir"] / "decision.json").write_text(
            "not valid json", encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=8,
        workspace=workspace, mfst=mfst, pipeline_id="test-strat-retry-3",
    )
    assert r.failure_reason == "strategist_schema_invalid"
    assert len(calls) == 1  # no retry on parse fail


def test_run_strategist_verify_retry_disabled_via_env(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASTERISM_STRATEGIST_VERIFY_RETRY=0 disables the retry — first
    verify failure returns immediately."""
    _insert_root(conn)
    monkeypatch.setenv("ASTERISM_STRATEGIST_VERIFY_RETRY", "0")
    calls: list[dict] = []

    def fake_spawn(**kw):
        calls.append(kw)
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({"kind": "Inject", "pipeline": "Backward",
                        "target_goal_id": 9999, "brief": "stale"}),
            encoding="utf-8")
        return 0

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=9,
        workspace=workspace, mfst=mfst, pipeline_id="test-strat-retry-4",
    )
    assert r.failure_reason == "strategist_schema_invalid"
    assert len(calls) == 1  # no retry when env disables


# ---------------------------------------------------------------------
# run_forward — full chain with mocked spawn_llm + LSP verify
# ---------------------------------------------------------------------

@pytest.fixture
def mock_lsp_verify(monkeypatch: pytest.MonkeyPatch):
    """Stub gateway_lifecycle.verify_file to always pass with no errors.
    Phase 2 Forward calls this in self_verify; bypass real gateway for
    unit tests."""
    from Tooling.lsp import lifecycle as gateway_lifecycle
    def fake_verify(target_path, **kw):
        return {
            "ok": True, "diagnostics": [], "diagnostic_count": 0,
            "olean_written": False, "olean_path": None,
            "axioms": None, "axiom_error": None,
        }
    monkeypatch.setattr(gateway_lifecycle, "verify_file", fake_verify)


def test_run_forward_commits_new_lemma(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Forward agent produces new_<slug>.lean with sorry body; commit
    inserts goal(origin='forward', status='open') for future BFS."""
    _insert_root(conn)
    pipeline_id = "test-fwd-1"

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: useful intermediate.\n"
            "-- entry_kind: Backward\n"
            "theorem my_lemma : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id=pipeline_id,
    )
    assert r.outcome == "success"
    # New goal inserted
    g = conn.execute(
        "SELECT origin, status, entry_kind, slug FROM goals"
        " WHERE problem='p' AND origin='forward'"
    ).fetchone()
    assert g is not None
    assert g["origin"] == "forward"
    assert g["status"] == "open"
    assert g["entry_kind"] == "Backward"
    assert g["slug"] == "my_lemma"


def test_run_forward_wires_lsp_session(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Asymmetry fix (Tier 1+2): Forward now spawns through run_lsp_edit_loop
    with an MCP session (`mcp_config_path` set), so the validate_file /
    apply_edit tools forward.md documents actually exist — previously Forward
    spawned blind (mcp_config_path=None) and those instructions were dead.
    Also asserts the fixed `new_forward.lean` target is cold-seeded with an
    import-enriched scaffold the agent edits into."""
    _insert_root(conn)
    captured: dict = {}

    def fake_spawn(**kw):
        captured.update(kw)
        # run_lsp_edit_loop's cold_prep seeded new_forward.lean before spawn.
        captured["seed"] = (
            kw["attempts_dir"] / "new_forward.lean"
        ).read_text(encoding="utf-8")
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: x.\n"
            "-- entry_kind: Backward\n"
            "theorem wired : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-lsp",
    )
    assert r.outcome == "success"
    # The LSP session is wired (the core of the asymmetry fix).
    assert captured.get("mcp_config_path") is not None
    # Cold seed: import-enriched scaffold, no premature declaration.
    assert "import Mathlib" in captured["seed"]
    assert "namespace Problems.p" in captured["seed"]
    assert "theorem" not in captured["seed"]


def test_run_forward_decline_path(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Agent ships a decline file (Library sufficient) →
    forward_no_new_goal/agent declined; no goal inserted."""
    _insert_root(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- decline: library_sufficient\n"
            "-- ## Why\n"
            "-- existing covers it\n"
            "theorem _forward_decline : True := by trivial\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-2",
    )
    # Phase 2 + retry helper: explicit decline is mapped to
    # `agent_declined` so the retry loop treats it as terminal — same
    # treatment as Builder's needs_decomposition. Pre-retry the
    # outcome was `forward_no_new_goal`; after wiring through
    # `run_with_session_retries` the helper requires a distinct
    # terminal failure_reason to short-circuit retries.
    assert r.outcome == "failed"
    assert r.failure_reason == "agent_declined"
    assert "agent declined" in r.failure_detail
    # No new goal inserted
    g = conn.execute(
        "SELECT COUNT(*) AS n FROM goals WHERE problem='p' AND origin='forward'"
    ).fetchone()
    assert g["n"] == 0


def test_run_forward_falls_back_to_stray_new_file(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Robustness: if the agent writes a differently-named new_*.lean (e.g. a
    thinking-trap rescue takeover whose generic prompt still says
    `new_<slug>.lean`, or a stray Write) instead of editing the seeded
    new_forward.lean, parse falls back to it rather than reading the
    un-edited seed."""
    _insert_root(conn)

    def fake_spawn(**kw):
        # Leave the seeded new_forward.lean untouched; write a stray file.
        (kw["attempts_dir"] / "new_stray.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: stray write.\n"
            "-- entry_kind: Backward\n"
            "theorem stray_lemma : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-stray",
    )
    assert r.outcome == "success"
    g = conn.execute(
        "SELECT slug FROM goals WHERE problem='p' AND origin='forward'"
    ).fetchone()
    assert g is not None and g["slug"] == "stray_lemma"


def test_run_forward_vocab_guard_is_defs_conditional(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Phase 6 — the Manifest-vocabulary guard on non-theorem kinds only
    applies when the problem ships Defs.lean (statement-vocabulary is
    user-owned there). A pure-NL Manifest NAMES the very defs it asks
    Forward to produce; rejecting them made pure-NL dead-on-arrival."""
    _insert_root(conn)
    mfst_nl = manifest.Manifest(
        problem="p", statement="define cube_boundary and prove its shape")

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: deliverable def named by the Manifest.\n"
            "def cube_boundary : Nat := 0\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    # No Defs.lean → guard skipped; the Manifest-named def commits
    # (sorry-free def → immediate 'proved').
    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst_nl,
        pipeline_id="test-fwd-vocab-1",
    )
    assert r.outcome == "proved"

    # Defs.lean present → same def is user-owned vocabulary; rejected.
    (workspace / "Problems" / "p" / "Defs.lean").write_text(
        "namespace Problems.p\nend Problems.p\n", encoding="utf-8")
    r2 = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst_nl,
        pipeline_id="test-fwd-vocab-2",
    )
    assert r2.outcome in ("failed", "exhausted")
    assert r2.failure_reason == "forward_no_new_goal"
    assert "Manifest statement" in (r2.failure_detail or "")


def test_run_forward_rejects_sorry_bearing_inferred_type_def(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Bug-B mirror (sphere_homology 2026-07-04): a sorry-bearing def with
    an INFERRED return type is un-decomposable (Backward's signature lock
    needs a top-level type colon) — it must be rejected at Forward commit
    with actionable feedback, not persisted to burn 5 attempts on
    `parent_stub_not_decomposable`."""
    _insert_root(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: assemble the iso.\n"
            "-- entry_kind: Backward\n"
            "noncomputable def bad_iso {R : Type} (A : Set R) :=\n"
            "  Iso.refl (by sorry)\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-inferred",
    )
    assert r.outcome in ("failed", "exhausted")
    assert r.failure_reason == "forward_no_new_goal"
    assert "type ascription" in (r.failure_detail or "")
    # Nothing persisted.
    assert conn.execute(
        "SELECT count(*) FROM goals WHERE problem='p' AND origin='forward'"
    ).fetchone()[0] == 0


def test_run_forward_inferred_type_def_passes_with_oracle_signature(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """decl-#2 dissolution: the same inferred-type sorry-bearing def is
    ACCEPTED when the candidate elaboration's decl_info supplies a
    splittable ppSignature — the goal enters BFS and its statement is the
    kernel-true pp conclusion (Backward's skeleton reconstructs from the
    same signature at decompose time)."""
    _insert_root(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: assemble the iso.\n"
            "-- entry_kind: Backward\n"
            "noncomputable def good_iso {R : Type} (A : Set R) :=\n"
            "  (by sorry : A = A)\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = {"startLine": 1, "startCol": 0, "endLine": 1, "endCol": 40}
    sel = {"startLine": 1, "startCol": 8, "endLine": 1, "endCol": 9}
    info = {
        "commands": [{"kind": "Lean.Parser.Command.declaration",
                      "range": r, "declNames": []}],
        "decls": [{
            "fqName": "Problems.p.good_iso",
            "userName": "Problems.p.good_iso",
            "kind": "def", "isProp": False, "isNoncomputable": True,
            "isProtected": False, "isPrivate": False, "isInstance": False,
            "signature": "Problems.p.good_iso {R : Type} (A : Set R) : A = A",
            "docstring": None, "cmdIdx": 0, "range": r, "selection": sel,
        }],
    }

    def fake_verify(target_path, **kw):
        return {
            "ok": True, "diagnostic_count": 0, "diagnostics": [],
            "olean_written": False, "olean_path": None,
            "axioms": None, "axiom_error": None,
            "decl_info": info if kw.get("decl_info") else None,
            "decl_info_error": None,
        }
    from Tooling.lsp import lifecycle as gateway_lifecycle
    monkeypatch.setattr(gateway_lifecycle, "verify_file", fake_verify)

    res = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-inferred-ok",
    )
    assert res.outcome == "success", res.failure_detail
    g = conn.execute(
        "SELECT * FROM goals WHERE problem='p' AND origin='forward'"
    ).fetchone()
    assert g is not None
    assert g["statement"] == "A = A"


def test_run_forward_no_output(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Agent rc=0 but no new_*.lean every retry → `exhausted` after
    FORWARD_RETRY_BUDGET attempts. Pre-retry this returned 'failed'
    directly; the retry refactor (see `run_forward`'s helper wiring)
    treats no-output as retryable, then exhausts when no attempt
    produces output."""
    _insert_root(conn)
    spawn_calls = {"n": 0}

    def fake_spawn(**kw):
        spawn_calls["n"] += 1
        return 0  # nothing produced
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-3",
    )
    assert r.outcome == "exhausted"
    assert r.failure_reason == "forward_no_new_goal"
    # Retry actually happened — not a single-shot.
    from Tooling.core import dispatcher
    assert spawn_calls["n"] == dispatcher.FORWARD_RETRY_BUDGET


def test_run_forward_consumes_strategist_brief(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Forward with decision_id reads brief and injects it into
    Context.md via compile_forward_context."""
    _insert_root(conn)
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, created_at,"
        " updated_at)"
        " VALUES ('p', 1, 'routine', 'Inject',"
        " '## Need\\nFooLemma', '{\"pipeline\": \"Forward\"}', ?, ?)",
        (ts, ts),
    )
    did = int(cur.lastrowid)
    conn.commit()

    captured_context: list[str] = []
    def fake_spawn(**kw):
        ctx_path = kw["attempts_dir"] / "Context.md"
        captured_context.append(ctx_path.read_text(encoding="utf-8"))
        # Agent declines so test isolates context check
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n-- decline: library_sufficient\n"
            "theorem _forward_decline : True := by trivial\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-4", decision_id=did,
    )
    assert captured_context
    assert "FooLemma" in captured_context[0]
    assert "## Strategist brief" in captured_context[0]
    # Forward gets the proved-lemma inventory + alive goals (so it does not
    # restate one and get dedup-rejected), but NOT the full decomposition
    # tree — Forward writes one generic lemma from the brief + ## Library,
    # it does not navigate goal structure (framework_backlog #3).
    assert "## Library" in captured_context[0]
    assert "## Active goals" in captured_context[0]
    assert "## TREE" not in captured_context[0]
    assert "## Forward\n" not in captured_context[0]


# ---------------------------------------------------------------------
# run_forward — Point 3: dedupe hit on a PROVED canonical aliases through
# (mirror of Backward) instead of declining `forward_no_new_goal`.
# ---------------------------------------------------------------------

def _insert_proved_canonical(conn: sqlite3.Connection, workspace: Path, *,
                             slug: str, statement: str = "True") -> int:
    """A proved Forward-origin canonical with a real lean file, the kind a
    Point-3 alias delegates to."""
    rel = f"Problems/p/proofs/L_{slug}.lean"
    (workspace / rel).write_text(
        "import Mathlib\nnamespace Problems.p\n"
        f"theorem {slug} : {statement} := trivial\nend Problems.p\n",
        encoding="utf-8")
    gid = db.insert_goal(
        conn, problem="p", slug=slug, lean_path=rel,
        statement=statement, origin="forward", depth=0,
        entry_kind="Backward",
    )
    db.update_goal_status(conn, gid, "proved")
    conn.commit()
    return gid


def test_run_forward_dedupe_alias_registers_proved_alias(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Point 3: a Forward dedupe hit on a PROVED in-DB canonical no longer
    declines (`forward_no_new_goal`) — it registers the lemma as a proved
    alias delegating to that canonical (mirror of Backward), breaking the
    reshape→re-inject spin (P13 4231/4261/...)."""
    from Tooling.quality import dedupe
    _insert_root(conn)
    canon_id = _insert_proved_canonical(conn, workspace, slug="canon")

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: restates canon.\n"
            "-- entry_kind: Backward\n"
            "theorem my_alias : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    # Force the dedupe verdict — the real probe needs lake.
    monkeypatch.setattr(
        dedupe, "find_canonicals_batch",
        lambda *a, **k: [dedupe.CanonicalMatch(goal_id=canon_id, kind="alias")],
    )

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-alias",
    )
    assert r.outcome == "proved"
    g = conn.execute(
        "SELECT status, alias_target_id, origin FROM goals"
        " WHERE problem='p' AND slug='my_alias'"
    ).fetchone()
    assert g is not None
    assert g["status"] == "proved"
    assert g["alias_target_id"] == canon_id
    assert g["origin"] == "forward"
    # The alias file delegates to the canonical via `apply`.
    alias_file = (workspace / "Problems" / "p" / "proofs"
                  / "L_my_alias.lean").read_text(encoding="utf-8")
    assert "apply canon <;> assumption" in alias_file
    assert "import Problems.p.proofs.L_canon" in alias_file


def test_run_forward_dedupe_library_alias_no_alias_target(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Point 3 (library tier): a hit on a proved `Library/` decl registers
    a proved alias delegating to the fully-qualified name — and records NO
    `alias_target_id` (no in-DB goal for prune to retain)."""
    from Tooling.quality import dedupe
    _insert_root(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: restates a Library decl.\n"
            "-- entry_kind: Backward\n"
            "theorem lib_alias : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(
        dedupe, "find_canonicals_batch",
        lambda *a, **k: [dedupe.CanonicalMatch(
            goal_id=-1, kind="library_alias",
            library_module="Library.Foo",
            library_fqn="Library.Foo.bar")],
    )

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-libalias",
    )
    assert r.outcome == "proved"
    g = conn.execute(
        "SELECT status, alias_target_id FROM goals"
        " WHERE problem='p' AND slug='lib_alias'"
    ).fetchone()
    assert g is not None
    assert g["status"] == "proved"
    assert g["alias_target_id"] is None
    alias_file = (workspace / "Problems" / "p" / "proofs"
                  / "L_lib_alias.lean").read_text(encoding="utf-8")
    assert "apply @Library.Foo.bar <;> assumption" in alias_file
    assert "import Library.Foo" in alias_file


def test_run_forward_dedupe_alias_build_fails_falls_back_to_novel(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Point 3 fallback: when the alias body fails to build (the
    bare-namespace dedupe probe was a false positive, or there is a real
    gap), the Forward commits the original body as a novel open goal —
    no proved alias is recorded. (Mirror of Backward's build-verify
    fallback, backward.py:1251-1267.)"""
    from Tooling.quality import dedupe
    from Tooling.lsp import lifecycle as gateway_lifecycle
    _insert_root(conn)
    canon_id = _insert_proved_canonical(conn, workspace, slug="canon2")

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: genuinely novel lemma.\n"
            "-- entry_kind: Backward\n"
            "theorem my_novel : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(
        dedupe, "find_canonicals_batch",
        lambda *a, **k: [dedupe.CanonicalMatch(goal_id=canon_id, kind="alias")],
    )

    # self_verify (the agent's original sorry body) passes; the alias
    # build (delegation body `apply canon2 <;> assumption`) fails — the
    # probe was a false positive. Both verifies run on the pipeline's OWN
    # slot (verify_in_session; unit tests always hold the conftest
    # /register stub token), whose contract is CONTENT-based — there is
    # no target path to discriminate on, so discriminate on the body.
    _OK = {
        "ok": True, "diagnostics": [], "diagnostic_count": 0,
        "olean_written": False, "olean_path": None,
        "axioms": None, "axiom_error": None,
    }
    _APPLY_FAIL = {"ok": False, "error": None, "diagnostics": [
        {"severity": "error", "message": "apply failed to unify"}]}

    def fake_verify(target_path, **kw):
        # borrow fallback (token absent) — same discrimination by path.
        in_proofs = "proofs" in Path(target_path).parts
        return dict(_APPLY_FAIL) if in_proofs else dict(_OK)
    monkeypatch.setattr(gateway_lifecycle, "verify_file", fake_verify)

    def fake_verify_session(token, content, **kw):
        return (dict(_APPLY_FAIL) if "apply canon2" in content
                else dict(_OK))
    monkeypatch.setattr(
        gateway_lifecycle, "verify_in_session", fake_verify_session)

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-fallback",
    )
    assert r.outcome == "success"
    g = conn.execute(
        "SELECT status, alias_target_id FROM goals"
        " WHERE problem='p' AND slug='my_novel'"
    ).fetchone()
    assert g is not None
    assert g["status"] == "open"
    assert g["alias_target_id"] is None
    # The novel commit wrote the agent's original body, not an alias.
    novel = (workspace / "Problems" / "p" / "proofs"
             / "L_my_novel.lean").read_text(encoding="utf-8")
    assert "sorry" in novel
    assert "apply canon2" not in novel


# ---------------------------------------------------------------------
# run_forward — #2 reuse: a dedupe hit on an alive/parked (NON-proved)
# in-problem twin repoints the inject instead of minting a duplicate.
# ---------------------------------------------------------------------

def _insert_inject_decision(conn: sqlite3.Connection) -> int:
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, payload, created_at,"
        " updated_at)"
        " VALUES ('p', 1, 'routine', 'Inject', 'b',"
        " '{\"pipeline\": \"Forward\"}', ?, ?)",
        (ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def _forward_dup_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- Forward rationale: accidental dup of an existing goal.\n"
            "-- entry_kind: Backward\n"
            "theorem dup : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)


def test_run_forward_decline_stashes_why_on_decision(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """#4 — a Forward decline's `## Why` reasoning is stashed on the
    originating Inject decision's `outcome_detail` so the Strategist's
    next wake sees WHY the brief was declined, not just
    `failed:agent_declined`."""
    _insert_root(conn)
    did = _insert_inject_decision(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new_forward.lean").write_text(
            "namespace Problems.p\n"
            "-- decline: library_sufficient\n"
            "-- ## Why\n"
            "-- Brief asked for foo_bridge; Mathlib's extDerivWithin_apply\n"
            "-- already covers it.\n"
            "theorem _forward_decline : True := by trivial\n"
            "end Problems.p\n",
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-decline-why", decision_id=did)
    assert r.failure_reason == "agent_declined"
    assert "extDerivWithin_apply" in r.failure_detail
    od = conn.execute(
        "SELECT outcome_detail FROM strategist_decisions WHERE id=?",
        (did,)).fetchone()["outcome_detail"]
    assert od is not None and "extDerivWithin_apply" in od


def test_run_forward_reuse_repoints_inject_to_open_goal(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """#2 — Forward lemma matches an alive OPEN in-problem goal X: don't
    mint a duplicate; repoint the inject at X (rides X's lifecycle), no
    new goal created."""
    from Tooling.quality import dedupe
    _insert_root(conn)
    x = db.insert_goal(
        conn, problem="p", slug="existing_x",
        lean_path="Problems/p/proofs/L_existing_x.lean", statement="True",
        origin="backward", depth=1, entry_kind="Builder")
    did = _insert_inject_decision(conn)
    _forward_dup_spawn(monkeypatch)
    monkeypatch.setattr(
        dedupe, "find_canonicals_batch",
        lambda *a, **k: [dedupe.CanonicalMatch(goal_id=x, kind="reuse")])

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-reuse-open", decision_id=did)
    assert r.outcome == "success"
    assert r.produced_goal_id == x
    # No duplicate goal created.
    n = conn.execute(
        "SELECT COUNT(*) c FROM goals WHERE problem='p' AND slug='dup'"
    ).fetchone()["c"]
    assert n == 0
    # Inject repointed at X; X untouched (still open, not detached).
    pg = conn.execute(
        "SELECT produced_goal_id FROM strategist_decisions WHERE id=?",
        (did,)).fetchone()["produced_goal_id"]
    assert pg == x
    assert db.get_goal(conn, x)["status"] == "open"


def test_run_forward_reuse_revives_and_detaches_shelved_goal(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """#2 — Forward lemma matches a SHELVED in-problem twin: repoint the
    inject + revive the twin (shelved→open) and detach it so it dispatches
    standalone (no host strategy to give it a live path)."""
    from Tooling.quality import dedupe
    _insert_root(conn)
    x = db.insert_goal(
        conn, problem="p", slug="parked_x",
        lean_path="Problems/p/proofs/L_parked_x.lean", statement="True",
        origin="backward", depth=1, entry_kind="Builder")
    db.update_goal_status(conn, x, "shelved")
    conn.commit()
    did = _insert_inject_decision(conn)
    _forward_dup_spawn(monkeypatch)
    monkeypatch.setattr(
        dedupe, "find_canonicals_batch",
        lambda *a, **k: [dedupe.CanonicalMatch(goal_id=x, kind="reuse")])

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-reuse-shelved", decision_id=did)
    assert r.outcome == "success"
    assert r.produced_goal_id == x
    gx = db.get_goal(conn, x)
    assert gx["status"] == "open"        # revived
    assert gx["detached"] == 1           # dispatch standalone
    pg = conn.execute(
        "SELECT produced_goal_id FROM strategist_decisions WHERE id=?",
        (did,)).fetchone()["produced_goal_id"]
    assert pg == x


def test_run_forward_reuse_parks_alongside_confirmshelve_goal(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """#2 — Forward lemma matches a ConfirmShelve-PARKED twin: repoint the
    inject but do NOT revive it. The twin is deliberately held pending its
    injected prereqs; the repointed inject parks alongside (rides its
    lifecycle, settles when the Strategist re-engages it). Reopening it early
    would re-dispatch before prereqs exist → re-fail → re-shelve mini-spin."""
    from Tooling.quality import dedupe
    _insert_root(conn)
    x = db.insert_goal(
        conn, problem="p", slug="parked_cs",
        lean_path="Problems/p/proofs/L_parked_cs.lean", statement="True",
        origin="backward", depth=1, entry_kind="Builder")
    db.update_goal_status(conn, x, "shelved")
    # Latest decision targeting x is a ConfirmShelve → parked (not cascade).
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, created_at, updated_at)"
        " VALUES ('p', 1, 'pending_review', 'ConfirmShelve', ?, ?, ?)",
        (x, db.now(), db.now()))
    conn.commit()
    did = _insert_inject_decision(conn)
    _forward_dup_spawn(monkeypatch)
    monkeypatch.setattr(
        dedupe, "find_canonicals_batch",
        lambda *a, **k: [dedupe.CanonicalMatch(goal_id=x, kind="reuse")])

    r = forward.run_forward(
        conn, problem="p", workspace=workspace, mfst=mfst,
        pipeline_id="test-fwd-reuse-parked", decision_id=did)
    assert r.outcome == "success"
    assert r.produced_goal_id == x
    gx = db.get_goal(conn, x)
    assert gx["status"] == "shelved"     # NOT revived — stays parked
    assert gx["detached"] == 0           # not detached either
    pg = conn.execute(
        "SELECT produced_goal_id FROM strategist_decisions WHERE id=?",
        (did,)).fetchone()["produced_goal_id"]
    assert pg == x                       # inject still repointed (parks alongside)
