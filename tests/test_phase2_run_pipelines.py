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
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)",
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
    commit records audit row + sets bootstrap_done; run returns
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
        conn, problem="p", trigger_kind="first_launch", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id=pipeline_id,
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "strategist_noop"
    # Audit row exists
    row = conn.execute(
        "SELECT decision_kind FROM strategist_decisions WHERE problem='p'"
    ).fetchone()
    assert row["decision_kind"] == "Noop"
    # bootstrap_done flipped
    p = conn.execute(
        "SELECT bootstrap_done FROM problems WHERE name='p'"
    ).fetchone()
    assert p["bootstrap_done"] == 1


def test_run_strategist_inject_enqueues_forward(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strategist Inject(Forward, briefs=[...]): commit enqueues
    Forward on problem with decision_id FK (unified Phase 2.5; even
    a 1-element briefs list goes through the batch helper)."""
    _insert_root(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({
                "kind": "Inject", "pipeline": "Forward",
                "briefs": ["## Need\nA contour lemma."],
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
        (kw["attempts_dir"] / "new_my_lemma.lean").write_text(
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


def test_run_forward_decline_path(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
    mock_lsp_verify,
) -> None:
    """Agent ships a decline file (Library sufficient) →
    forward_no_new_goal/agent declined; no goal inserted."""
    _insert_root(conn)

    def fake_spawn(**kw):
        (kw["attempts_dir"] / "new__forward_decline.lean").write_text(
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
        (kw["attempts_dir"] / "new__decline.lean").write_text(
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
