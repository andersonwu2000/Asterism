"""serve API contract tests (frontend charter §2: API layer is pytest-
covered; no toolchain spawn — everything runs against a tmp workspace).

Covers the iron rules observable from outside: reads work on a
read-only connection (schema-behind → 503, missing DB → graceful empty
states), writes flow through the state/CLI chokepoints (amend resolve,
ingest sign-off) with their side effects visible in the DB.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Tooling.serve.app import create_app
from Tooling.state import db


# ---------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


def _open_db(workspace: Path) -> sqlite3.Connection:
    conn = db.connect(workspace / "asterism.db")
    db.init_schema(conn)
    return conn


def _client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _add_problem(conn: sqlite3.Connection, name: str, **cols) -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()))
    for k, v in cols.items():
        conn.execute(f"UPDATE problems SET {k} = ? WHERE name = ?", (v, name))
    conn.commit()


def _add_decision(conn: sqlite3.Connection, problem: str, *,
                  kind: str = "Noop", outcome: str | None = "success",
                  payload: dict | None = None, reason: str = "") -> int:
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, reason, payload, outcome,"
        " created_at, updated_at) VALUES (?, 0, 'routine', ?, '', ?, ?, ?,"
        " ?, ?)",
        (problem, kind, reason, json.dumps(payload or {}), outcome, ts, ts))
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------
# empty / degraded states
# ---------------------------------------------------------------------

def test_meta_fresh_workspace_no_db(workspace: Path) -> None:
    r = _client(workspace).get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "missing"
    assert body["inbox_count"] == 0
    assert body["daemon"]["running"] is False


def test_meta_never_creates_the_db(workspace: Path) -> None:
    """Iron rule regression: the read surface must not write. db.connect()
    CREATES a missing sqlite file — the daemon-status path did exactly
    that from /api/meta, making every fresh workspace look
    schema-behind (0-byte DB at user_version 0)."""
    c = _client(workspace)
    c.get("/api/meta")
    c.get("/api/daemon")
    c.get("/api/problems")
    assert not (workspace / "asterism.db").exists()
    assert c.get("/api/meta").json()["daemon"]["in_flight_leases"] == 0


def test_board_fresh_workspace_is_empty_not_error(workspace: Path) -> None:
    r = _client(workspace).get("/api/problems")
    assert r.status_code == 200
    assert r.json() == {"problems": []}


def test_inbox_and_library_fresh_workspace(workspace: Path) -> None:
    c = _client(workspace)
    assert c.get("/api/inbox").json() == {"amends": [], "signoffs": []}
    assert c.get("/api/library").json() == {"problems": []}
    assert c.get("/api/telemetry/usage").json() == {"problems": []}


def test_schema_behind_serves_503_upgrade_required(workspace: Path) -> None:
    conn = _open_db(workspace)
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()
    c = _client(workspace)
    r = c.get("/api/problems")
    assert r.status_code == 503
    assert "UPGRADE_REQUIRED" in r.json()["detail"]
    assert _client(workspace).get("/api/meta").json()["db"] == "behind"


# ---------------------------------------------------------------------
# board aggregation
# ---------------------------------------------------------------------

def test_board_status_chips(workspace: Path) -> None:
    conn = _open_db(workspace)
    # proving: dispatchable open root goal
    _add_problem(conn, "proving_p")
    db.insert_goal(conn, problem="proving_p", slug="main",
                   lean_path="Problems/proving_p/proofs/main.lean",
                   statement="True", origin="root")
    # idle: no goals at all, no progress → presentation refinement of
    # the engine's stall signal (never-launched ≠ needs attention)
    _add_problem(conn, "idle_p")
    # stalled WITH progress: proved work exists but nothing dispatchable
    _add_problem(conn, "stalled_p")
    db.insert_goal(conn, problem="stalled_p", slug="done",
                   lean_path="Problems/stalled_p/proofs/done.lean",
                   statement="True", origin="root", status="proved")
    # awaiting_human beats everything else
    _add_problem(conn, "amend_p")
    _add_decision(conn, "amend_p", kind="RequestUserAmend",
                  outcome="awaiting_human",
                  payload={"file": "Manifest.md", "proposed_body": "x",
                           "question": "q"})
    # sign-off pending (ingested + paused)
    _add_problem(conn, "signoff_p", ingest_signoff_pending=1,
                 ingested_at=db.now())
    # terminal states
    _add_problem(conn, "ingested_p", ingested_at=db.now())
    _add_problem(conn, "bridged_p", ingested_at=db.now(),
                 library_bridged_at=db.now())
    conn.commit()
    conn.close()

    rows = {p["name"]: p for p in
            _client(workspace).get("/api/problems").json()["problems"]}
    assert rows["proving_p"]["status"] == "proving"
    assert rows["proving_p"]["goals"]["open"] == 1
    assert rows["idle_p"]["status"] == "idle"
    assert rows["stalled_p"]["status"] == "stalled"
    # board and detail must agree on the chip (idle refinement lives in
    # both paths)
    c = _client(workspace)
    assert c.get("/api/problems/idle_p").json()["status"] == "idle"
    assert c.get("/api/problems/stalled_p").json()["status"] == "stalled"
    # queued work (the between-batches Strategist wake) suppresses the
    # red flicker: stalled + queue row → proving, on both surfaces
    conn = db.connect(workspace / "asterism.db")
    db.enqueue(conn, kind="Strategist", target_id="stalled_p",
               target_kind="Problem", problem="stalled_p")
    conn.commit()
    conn.close()
    rows2 = {p["name"]: p for p in
             c.get("/api/problems").json()["problems"]}
    assert rows2["stalled_p"]["status"] == "proving"
    assert c.get("/api/problems/stalled_p").json()["status"] == "proving"
    assert rows["amend_p"]["status"] == "awaiting_human"
    assert rows["signoff_p"]["status"] == "signoff_pending"
    assert rows["ingested_p"]["status"] == "ingested"
    assert rows["bridged_p"]["status"] == "bridged"


# ---------------------------------------------------------------------
# problem detail + goal drill-down
# ---------------------------------------------------------------------

def test_problem_detail_shape(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="main",
                         lean_path="Problems/p/proofs/main.lean",
                         statement="True", origin="root")
    sub = db.insert_goal(conn, problem="p", slug="lemma_a",
                         lean_path="Problems/p/proofs/lemma_a.lean",
                         statement="1 = 1", origin="backward")
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at) VALUES (?, 'x', 'proposed', 'test', ?)", (gid, ts))
    sid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, sub))
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('pl_1', 'Builder', ?, 'Goal', 'failed', 'agent_timeout',"
        " ?, ?)", (str(sub), ts, ts))
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, ts) VALUES (?, 'Goal', 'pl_1', 'agent_timeout', ?)",
        (sub, ts))
    _add_decision(conn, "p", kind="Noop", reason="thinking")
    conn.commit()
    conn.close()
    proofs = workspace / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / "main.lean").write_text("theorem main : True := trivial",
                                      encoding="utf-8")

    c = _client(workspace)
    d = c.get("/api/problems/p").json()
    assert {g["slug"] for g in d["goals"]} == {"main", "lemma_a"}
    lemma = next(g for g in d["goals"] if g["slug"] == "lemma_a")
    assert lemma["dead_attempts"] == 1
    assert d["strategies"][0]["goal_id"] == gid
    assert d["strategy_edges"][0] == {
        "strategy_id": sid, "subgoal_id": sub, "position": 0}
    assert d["decisions"][0]["decision_kind"] == "Noop"
    assert d["proof_files"] == ["main.lean"]

    g = c.get(f"/api/problems/p/goals/{sub}").json()
    assert g["dead_attempts"][0]["failure_reason"] == "agent_timeout"

    assert c.get("/api/problems/nope").status_code == 404
    assert c.get("/api/problems/p/goals/99999").status_code == 404


def test_strategy_detail_endpoint(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="main",
                         lean_path="Problems/p/proofs/main.lean",
                         statement="True", origin="root")
    sub = db.insert_goal(conn, problem="p", slug="lemma_a",
                         lean_path="Problems/p/proofs/lemma_a.lean",
                         statement="1 = 1", origin="backward")
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, proposal_md,"
        " created_by, created_at) VALUES (?, 'x', 'dead',"
        " '## Plan\ninduction on n', 'backward', ?)", (gid, ts))
    sid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, sub))
    conn.commit()
    conn.close()
    c = _client(workspace)
    d = c.get(f"/api/problems/p/strategies/{sid}").json()
    assert d["goal_slug"] == "main"
    assert d["status"] == "dead"
    assert "induction on n" in d["proposal_md"]
    assert d["subgoals"][0]["slug"] == "lemma_a"
    assert c.get("/api/problems/p/strategies/9999").status_code == 404
    # cross-problem access refused
    assert c.get(f"/api/problems/other/strategies/{sid}").status_code == 404


def test_problem_file_read_sandboxed(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    conn.close()
    pdir = workspace / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Defs.lean").write_text("def x := 1", encoding="utf-8")
    c = _client(workspace)
    r = c.get("/api/problems/p/file", params={"path": "Defs.lean"})
    assert r.json()["content"] == "def x := 1"
    # traversal + non-lean/md refused
    assert c.get("/api/problems/p/file",
                 params={"path": "../../pyproject.toml"}).status_code == 404
    assert c.get("/api/problems/p/file",
                 params={"path": "..\\..\\secrets.md"}).status_code == 404


# ---------------------------------------------------------------------
# inbox + amend resolution (write chokepoint)
# ---------------------------------------------------------------------

def _amend_fixture(workspace: Path) -> tuple[int, Path]:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    did = _add_decision(
        conn, "p", kind="RequestUserAmend", outcome="awaiting_human",
        payload={"file": "Manifest.md",
                 "proposed_body": "# proposed\nnew content\n",
                 "question": "apply this?"},
        reason="needs a stronger hypothesis")
    conn.close()
    pdir = workspace / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Manifest.md").write_text("# old\n", encoding="utf-8")
    (pdir / ".proposed_Manifest.md").write_text(
        "# proposed\nnew content\n", encoding="utf-8")
    return did, pdir


def test_inbox_lists_amend_with_both_bodies(workspace: Path) -> None:
    _amend_fixture(workspace)
    box = _client(workspace).get("/api/inbox").json()
    assert len(box["amends"]) == 1
    a = box["amends"][0]
    assert a["problem"] == "p"
    assert a["file"] == "Manifest.md"
    assert a["proposed_body"].startswith("# proposed")
    assert a["current_body"] == "# old\n"
    assert a["question"] == "apply this?"
    meta = _client(workspace).get("/api/meta").json()
    assert meta["inbox_count"] == 1


def test_amend_accept_writes_file_and_resumes(workspace: Path) -> None:
    did, pdir = _amend_fixture(workspace)
    c = _client(workspace)
    r = c.post(f"/api/inbox/amend/{did}/resolve",
               json={"action": "accept"})
    assert r.status_code == 200
    assert (pdir / "Manifest.md").read_text(
        encoding="utf-8") == "# proposed\nnew content\n"
    assert not (pdir / ".proposed_Manifest.md").exists()
    conn = db.connect(workspace / "asterism.db")
    row = conn.execute("SELECT outcome FROM strategist_decisions"
                       " WHERE id = ?", (did,)).fetchone()
    assert row["outcome"] == "accepted"
    # Strategist wake enqueued so the problem resumes promptly
    assert db.is_in_queue(conn, target_id="p", kind="Strategist")
    conn.close()
    # second resolve → conflict
    assert c.post(f"/api/inbox/amend/{did}/resolve",
                  json={"action": "accept"}).status_code == 409


def test_amend_accept_with_edited_body(workspace: Path) -> None:
    did, pdir = _amend_fixture(workspace)
    _client(workspace).post(
        f"/api/inbox/amend/{did}/resolve",
        json={"action": "accept", "body": "# operator-edited\n"})
    assert (pdir / "Manifest.md").read_text(
        encoding="utf-8") == "# operator-edited\n"


def test_amend_reject_leaves_file_untouched(workspace: Path) -> None:
    did, pdir = _amend_fixture(workspace)
    r = _client(workspace).post(
        f"/api/inbox/amend/{did}/resolve",
        json={"action": "reject", "reason": "wrong direction"})
    assert r.status_code == 200
    assert (pdir / "Manifest.md").read_text(encoding="utf-8") == "# old\n"
    assert not (pdir / ".proposed_Manifest.md").exists()
    conn = db.connect(workspace / "asterism.db")
    row = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert row["outcome"] == "rejected"
    assert row["outcome_detail"] == "wrong direction"
    conn.close()


def test_amend_bad_action_and_unknown_id(workspace: Path) -> None:
    did, _ = _amend_fixture(workspace)
    c = _client(workspace)
    assert c.post(f"/api/inbox/amend/{did}/resolve",
                  json={"action": "maybe"}).status_code == 409
    assert c.post("/api/inbox/amend/424242/resolve",
                  json={"action": "accept"}).status_code == 409


# ---------------------------------------------------------------------
# ingest sign-off (write chokepoint: cmd_approve/reject_ingest)
# ---------------------------------------------------------------------

def test_approve_ingest_via_api(workspace: Path, monkeypatch) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p", ingest_signoff_pending=1, ingested_at=db.now())
    conn.close()
    monkeypatch.chdir(workspace)  # chokepoints open the cwd-relative DB
    c = _client(workspace)
    assert c.get("/api/inbox").json()["signoffs"][0]["problem"] == "p"
    r = c.post("/api/problems/p/approve-ingest")
    assert r.status_code == 200
    conn = db.connect(workspace / "asterism.db")
    assert not db.problem_ingest_signoff_pending(conn, "p")
    assert db.is_in_queue(conn, target_id="p", kind="Librarian")
    conn.close()
    # not pending anymore → 409
    assert c.post("/api/problems/p/approve-ingest").status_code == 409


def test_reject_ingest_via_api(workspace: Path, monkeypatch) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p", ingest_signoff_pending=1, ingested_at=db.now())
    conn.close()
    monkeypatch.chdir(workspace)
    r = _client(workspace).post("/api/problems/p/reject-ingest",
                                json={"reason": "missing claim B"})
    assert r.status_code == 200
    conn = db.connect(workspace / "asterism.db")
    row = conn.execute(
        "SELECT ingest_signoff_pending, ingested_at, strategist_directive"
        " FROM problems WHERE name = 'p'").fetchone()
    assert row["ingest_signoff_pending"] == 0
    assert row["ingested_at"] is None  # terminal judgment revoked
    assert "missing claim B" in row["strategist_directive"]
    assert db.is_in_queue(conn, target_id="p", kind="Strategist")
    conn.close()


# ---------------------------------------------------------------------
# review snapshot / telemetry / library
# ---------------------------------------------------------------------

def test_anchor_edges_derived_from_snapshot(workspace: Path) -> None:
    """Forward-only problems have no strategy edges; the detail endpoint
    derives dependency edges from the review snapshot's anchor closure
    (anchor → deliverable, matched by slug)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    a = db.insert_goal(conn, problem="p", slug="toy_reverse",
                       lean_path="Problems/p/proofs/a.lean",
                       statement="d", origin="forward", status="proved")
    d = db.insert_goal(conn, problem="p", slug="toy_reverse_involutive",
                       lean_path="Problems/p/proofs/d.lean",
                       statement="t", origin="forward", status="proved")
    db.set_review_snapshot(conn, "p", json.dumps({
        "deliverables": [{
            "slug": "toy_reverse_involutive", "ok": True,
            "anchors": [
                {"kind": "def", "module": "m",
                 "name": "Problems.p.toy_reverse"},
                # ctor attributes to its parent decl; duplicate pair folds
                {"kind": "ctor", "module": "m",
                 "name": "Problems.p.toy_reverse.mk"},
            ],
            "claims": [],
        }],
        "union_count": 1}))
    conn.commit()
    conn.close()
    body = _client(workspace).get("/api/problems/p").json()
    assert body["anchor_edges"] == [{"from": a, "to": d}]


def test_review_snapshot_roundtrip(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    db.set_review_snapshot(conn, "p", json.dumps(
        {"deliverables": [{"fq": "Problems.p.main", "ok": True}],
         "union_count": 3}))
    conn.commit()
    conn.close()
    c = _client(workspace)
    r = c.get("/api/problems/p/review")
    assert r.status_code == 200
    body = r.json()
    assert body["union_count"] == 3
    assert body["deliverables"][0]["ok"] is True
    assert body["stored_at"]
    assert c.get("/api/problems/unknown/review").status_code == 404


def test_telemetry_usage_aggregates(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    ts = db.now()
    for kind, out_tok in (("Forward", 100), ("Forward", 50), ("Builder", 7)):
        conn.execute(
            "INSERT INTO spawn_usage (pipeline_id, kind, problem,"
            " input_tokens, output_tokens, turns, wall_sec, ts)"
            " VALUES ('pl', ?, 'p', 10, ?, 1, 2.5, ?)",
            (kind, out_tok, ts))
    conn.commit()
    conn.close()
    rows = _client(workspace).get("/api/telemetry/usage").json()["problems"]
    p = rows[0]
    assert p["problem"] == "p"
    assert p["spawns"] == 3
    assert p["output_tokens"] == 157
    kinds = {k["kind"]: k for k in p["kinds"]}
    assert kinds["Forward"]["spawns"] == 2


def test_library_lists_bridged_decls(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p", library_bridged_at=db.now())
    ts = db.now()
    conn.execute(
        "INSERT INTO library_decls (problem, slug, lifecycle, target_file,"
        " target_name, signature, decl_kind, created_at, updated_at)"
        " VALUES ('p', 'main_thm', 'cleaned', 'Library/X.lean',"
        " 'Asterism.mainThm', 'theorem mainThm : True', 'theorem', ?, ?)",
        (ts, ts))
    conn.commit()
    conn.close()
    lib = _client(workspace).get("/api/library").json()
    assert lib["problems"][0]["problem"] == "p"
    assert lib["problems"][0]["decls"][0]["name"] == "Asterism.mainThm"


def test_review_refresh_async_job(workspace: Path, monkeypatch) -> None:
    """The refresh job recomputes + stores the snapshot off-request (the
    only gateway-legal path). Gateway is monkeypatched out (test fence)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    conn.close()

    from Tooling.quality import review as _review

    def fake_store(conn, ws, problem):  # noqa: ANN001
        db.set_review_snapshot(conn, problem, json.dumps(
            {"deliverables": [], "union_count": 0}))
        conn.commit()
        return True

    monkeypatch.setattr(_review, "store_review_snapshot", fake_store)
    c = _client(workspace)
    assert c.get("/api/problems/p/review").status_code == 404
    r = c.post("/api/problems/p/review/refresh")
    assert r.json()["state"] == "running"
    for _ in range(50):
        state = c.get("/api/problems/p/review/refresh").json()["state"]
        if state != "running":
            break
        import time as _t
        _t.sleep(0.1)
    assert state == "done"
    assert c.get("/api/problems/p/review").status_code == 200


def test_reject_decl_endpoint_calls_chokepoint(workspace: Path,
                                               monkeypatch) -> None:
    """Per-deliverable reject rides cmd_reject verbatim (gateway-heavy —
    structural test only, chokepoint monkeypatched)."""
    from Tooling.core import cli as _cli
    calls: list = []

    def fake_reject(args):  # noqa: ANN001
        calls.append((args.decl, args.problem, args.reason, args.dry_run))
        return 0

    monkeypatch.setattr(_cli, "cmd_reject", fake_reject)
    c = _client(workspace)
    r = c.post("/api/problems/p/reject-decl",
               json={"decl": "Problems.p.bad_lemma", "reason": "wrong"})
    assert r.status_code == 200
    assert calls == [("Problems.p.bad_lemma", "p", "wrong", False)]

    monkeypatch.setattr(_cli, "cmd_reject", lambda a: 1)
    assert c.post("/api/problems/p/reject-decl",
                  json={"decl": "x"}).status_code == 409


def test_paper_section_page_anchor(workspace: Path) -> None:
    pdir = workspace / "Papers" / "abc123"
    pdir.mkdir(parents=True)
    (pdir / "text.md").write_text(
        "# Title\n\n## p.1\nfirst page\n\n## p.2\nsecond page body\n\n"
        "## p.3\nthird\n", encoding="utf-8")
    c = _client(workspace)
    r = c.get("/api/papers/abc123/section", params={"anchor": "## p.2"})
    body = r.json()
    assert body["found"] is True
    assert "second page body" in body["content"]
    assert "third" not in body["content"]
    # free-text ref resolves to its containing page
    r2 = c.get("/api/papers/abc123/section",
               params={"anchor": "second page"})
    assert r2.json()["found"] is True
    assert "second page body" in r2.json()["content"]
    # unknown paper → 404; traversal refused
    assert c.get("/api/papers/nope/section").status_code == 404
    assert c.get("/api/papers/..%2Fabc123/section").status_code == 404


# ---------------------------------------------------------------------
# daemon status (read-only surface; start/stop covered at CLI level)
# ---------------------------------------------------------------------

def test_daemon_status_endpoint(workspace: Path) -> None:
    r = _client(workspace).get("/api/daemon")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False
    assert body["stopping"] is False


# ---------------------------------------------------------------------
# problem authoring (POST /api/problems/create)
# ---------------------------------------------------------------------

_MANIFEST = """---
problem: Test.ui_created
axioms_whitelist:
  - propext
forbidden_lemmas: []
library: true
---

# Test.ui_created — a UI-authored problem

## Statement

Prove something small.
"""


def test_create_problem_pure_nl(workspace: Path) -> None:
    c = _client(workspace)
    r = c.post("/api/problems/create",
               json={"name": "Test.ui_created", "manifest": _MANIFEST})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["problem"] == "Test.ui_created"
    assert "pure-NL" in body["message"]
    pdir = workspace / "Problems" / "Test" / "ui_created"
    assert (pdir / "Manifest.md").read_text(encoding="utf-8") == _MANIFEST
    assert (pdir / "proofs").is_dir()
    conn = db.connect(workspace / "asterism.db")
    row = conn.execute("SELECT manifest_path FROM problems WHERE name = ?",
                       ("Test.ui_created",)).fetchone()
    conn.close()
    assert row is not None
    assert row["manifest_path"] == "Problems/Test/ui_created/Manifest.md"
    # visible on the board immediately
    names = [p["name"] for p in c.get("/api/problems").json()["problems"]]
    assert "Test.ui_created" in names


def test_create_problem_duplicate_409(workspace: Path) -> None:
    c = _client(workspace)
    assert c.post("/api/problems/create",
                  json={"name": "Test.dup", "manifest": _MANIFEST
                        }).status_code == 200
    r = c.post("/api/problems/create",
               json={"name": "Test.dup", "manifest": _MANIFEST})
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


def test_create_problem_bad_name_422(workspace: Path) -> None:
    c = _client(workspace)
    for bad in ("", "1starts_with_digit", "has space", "trailing.", "a..b",
                "semi;colon"):
        r = c.post("/api/problems/create",
                   json={"name": bad, "manifest": _MANIFEST})
        assert r.status_code == 422, bad
    assert not (workspace / "Problems" / "has space").exists()


def test_create_problem_empty_manifest_422(workspace: Path) -> None:
    r = _client(workspace).post(
        "/api/problems/create",
        json={"name": "Test.empty", "manifest": "   \n"})
    assert r.status_code == 422
    assert not (workspace / "Problems" / "Test" / "empty").exists()


def test_create_problem_init_failure_rolls_back(
        workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from Tooling.core import cli as _cli
    monkeypatch.setattr(_cli, "init_problem",
                        lambda ws, name, **kw: (1, "FAIL: stubbed"))
    r = _client(workspace).post(
        "/api/problems/create",
        json={"name": "Test.rollback", "manifest": _MANIFEST})
    assert r.status_code == 422
    assert "stubbed" in r.json()["detail"]
    # the created directory is rolled back so a retry can succeed
    assert not (workspace / "Problems" / "Test" / "rollback").exists()


# ---------------------------------------------------------------------
# manifest read/update + structured create + config
# ---------------------------------------------------------------------

def test_create_problem_structured(workspace: Path) -> None:
    c = _client(workspace)
    r = c.post("/api/problems/create", json={
        "name": "Test.structured",
        "body": "# Test.structured\n\n## Statement\n\nProve it.\n",
        "settings": {"forbidden_lemmas": ["sperner*"], "library": True},
    })
    assert r.status_code == 200, r.text
    text = (workspace / "Problems" / "Test" / "structured" /
            "Manifest.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "problem: Test.structured" in text
    assert "- propext" in text            # default whitelist filled in
    assert "- sperner*" in text
    assert "library: true" in text
    assert "## Statement" in text


def test_manifest_get_and_update(workspace: Path) -> None:
    c = _client(workspace)
    c.post("/api/problems/create", json={
        "name": "Test.editme",
        "body": "# Test.editme\n\nOld body.\n",
        "settings": {"library": False},
    })
    got = c.get("/api/problems/Test.editme/manifest").json()
    assert got["settings"]["library"] is False
    assert "Old body." in got["body"]
    assert got["pending_amend"] is False
    r = c.post("/api/problems/Test.editme/manifest", json={
        "body": "\n# Test.editme\n\nNew body.\n",
        "settings": {"library": True, "forbidden_lemmas": ["kuhn*"]},
    })
    assert r.status_code == 200, r.text
    got2 = c.get("/api/problems/Test.editme/manifest").json()
    assert got2["settings"]["library"] is True
    assert got2["settings"]["forbidden_lemmas"] == ["kuhn*"]
    assert "New body." in got2["body"]
    # unknown frontmatter keys survive: problem: still present
    text = (workspace / "Problems" / "Test" / "editme" /
            "Manifest.md").read_text(encoding="utf-8")
    assert "problem: Test.editme" in text


def test_manifest_update_blocked_by_pending_amend(workspace: Path) -> None:
    c = _client(workspace)
    c.post("/api/problems/create", json={
        "name": "Test.locked", "body": "# Test.locked\n"})
    conn = _open_db(workspace)
    _add_decision(conn, "Test.locked", kind="RequestUserAmend",
                  outcome="awaiting_human",
                  payload={"file": "Manifest.md"})
    conn.close()
    r = c.post("/api/problems/Test.locked/manifest",
               json={"body": "\n# clobber\n"})
    assert r.status_code == 409
    assert "Inbox" in r.json()["detail"]


def test_config_get_and_set(workspace: Path) -> None:
    c = _client(workspace)
    got = c.get("/api/config").json()["settings"]
    keys = {row["key"] for row in got}
    assert "strategist.model" in keys and "dispatch.pool" in keys
    r = c.post("/api/config",
               json={"key": "strategist.model", "value": "claude-fable-5"})
    assert r.status_code == 200
    got2 = {row["key"]: row for row in
            c.get("/api/config").json()["settings"]}
    assert got2["strategist.model"]["yaml"] == "claude-fable-5"
    # bounds + allowlist enforced
    assert c.post("/api/config", json={
        "key": "dispatch.pool", "value": 999}).status_code == 422
    assert c.post("/api/config", json={
        "key": "gateway.port", "value": 1}).status_code == 422
