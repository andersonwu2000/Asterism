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
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)",
        (name, db.now()))
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
    # auth awareness rides meta (the login itself is Claude Code's own
    # first-run flow — the UI only knows the state and opens it)
    assert set(body["claude"]) == {"installed", "logged_in", "subscription"}


def test_claude_login_needs_the_cli(workspace: Path, monkeypatch) -> None:
    # patch the resolver, not shutil.which — claude_exe also probes
    # the CLI's known install homes on the real filesystem
    import Tooling.serve.app as _app
    monkeypatch.setattr(_app, "claude_exe", lambda: None)
    r = _client(workspace).post("/api/claude/login")
    assert r.status_code == 409
    # points at the setup wizard, not a script (install.bat retired)
    assert "setup" in r.json()["detail"]


def test_claude_logout_retires_the_session_file(
        workspace: Path, monkeypatch, tmp_path: Path) -> None:
    """Logout = renaming the local session file to a timestamped
    backup (reversible, never a delete). MUST run against a fake
    home — a test may never touch the real login."""
    import Tooling.serve.app as _app
    fake = tmp_path / "fakehome" / ".claude" / ".credentials.json"
    fake.parent.mkdir(parents=True)
    fake.write_text(json.dumps({"claudeAiOauth": {
        "accessToken": "x", "subscriptionType": "max"}}), encoding="utf-8")
    monkeypatch.setattr(_app, "_creds_path", lambda: fake)
    c = _client(workspace)
    st = c.get("/api/meta").json()["claude"]
    assert st["logged_in"] is True
    assert st["subscription"] == "max"
    r = c.post("/api/claude/logout")
    assert r.json()["logged_out"] is True
    assert not fake.exists()
    backups = list(fake.parent.glob(".credentials.json.bak-*"))
    assert len(backups) == 1
    assert c.get("/api/meta").json()["claude"]["logged_in"] is False
    # idempotent: a second logout reports, never errors
    assert c.post("/api/claude/logout").json()["logged_out"] is False


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
    assert c.get("/api/telemetry/usage").json() == {
        "problems": [], "window": "all", "since": None}


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
                  payload={"file": "charter", "proposed_body": "x",
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
    # "proving" is an engine-liveness claim: no daemon runs in this
    # test, so unfinished work reads paused, never proving
    assert rows["proving_p"]["status"] == "paused"
    assert rows["proving_p"]["goals"]["open"] == 1
    assert rows["idle_p"]["status"] == "idle"
    assert rows["stalled_p"]["status"] == "stalled"
    # board and detail must agree on the chip (refinements live in
    # both paths)
    c = _client(workspace)
    assert c.get("/api/problems/idle_p").json()["status"] == "idle"
    assert c.get("/api/problems/stalled_p").json()["status"] == "stalled"
    # queued work left behind without a live daemon is residue, not
    # motion: stalled + queue row still reads paused on both surfaces
    conn = db.connect(workspace / "asterism.db")
    db.enqueue(conn, kind="Strategist", target_id="stalled_p",
               target_kind="Problem", problem="stalled_p")
    conn.commit()
    conn.close()
    rows2 = {p["name"]: p for p in
             c.get("/api/problems").json()["problems"]}
    assert rows2["stalled_p"]["status"] == "paused"
    assert c.get("/api/problems/stalled_p").json()["status"] == "paused"
    assert rows["amend_p"]["status"] == "awaiting_human"
    assert rows["signoff_p"]["status"] == "signoff_pending"
    assert rows["ingested_p"]["status"] == "ingested"
    assert rows["bridged_p"]["status"] == "bridged"


def _fake_daemon(monkeypatch, *, pid: int = 4321,
                 scope: "str | None" = None,
                 started_at: "str | None" = None) -> None:
    """Make the serve layer see a live daemon (pid + scope)."""
    import Tooling.core.cli as _cli

    def fake_status(workspace):  # noqa: ANN001
        return {"running": True, "pid": pid, "scope": scope,
                "started_at": started_at or db.now(), "stopping": False,
                "in_flight_leases": 0}
    monkeypatch.setattr(_cli, "daemon_status", fake_status)


def test_board_proving_requires_live_daemon_on_scope(
        workspace: Path, monkeypatch) -> None:
    """The chip says "proving" iff a live daemon is scoped to the
    problem; a daemon busy elsewhere leaves it paused (the force-stop /
    two-problems-proving lie, 2026-07-07)."""
    conn = _open_db(workspace)
    _add_problem(conn, "mine")
    db.insert_goal(conn, problem="mine", slug="main",
                   lean_path="Problems/mine/proofs/main.lean",
                   statement="True", origin="root")
    _add_problem(conn, "other")
    db.insert_goal(conn, problem="other", slug="main",
                   lean_path="Problems/other/proofs/main.lean",
                   statement="True", origin="root")
    conn.commit()
    conn.close()

    _fake_daemon(monkeypatch, scope="mine")
    c = _client(workspace)
    rows = {p["name"]: p for p in
            c.get("/api/problems").json()["problems"]}
    assert rows["mine"]["status"] == "proving"
    assert rows["other"]["status"] == "paused"
    detail = c.get("/api/problems/mine").json()
    assert detail["status"] == "proving"
    assert detail["engine_working"] is True
    other = c.get("/api/problems/other").json()
    assert other["status"] == "paused"
    assert other["engine_working"] is False


def test_board_fresh_scoped_problem_reads_proving(
        workspace: Path, monkeypatch) -> None:
    """A freshly-Run problem has zero goals for minutes (Lean warm-up +
    bootstrap) — with a live daemon scoped to it, it must read proving,
    not idle (Test.Test3: the user pressed Run and the board showed
    nothing at all)."""
    conn = _open_db(workspace)
    _add_problem(conn, "fresh")
    conn.close()
    c = _client(workspace)
    rows = {p["name"]: p for p in
            c.get("/api/problems").json()["problems"]}
    assert rows["fresh"]["status"] == "idle"
    _fake_daemon(monkeypatch, scope="fresh")
    rows2 = {p["name"]: p for p in
             c.get("/api/problems").json()["problems"]}
    assert rows2["fresh"]["status"] == "proving"
    assert c.get("/api/problems/fresh").json()["status"] == "proving"


def test_board_in_flight_counts_only_live_daemon_leases(
        workspace: Path, monkeypatch) -> None:
    """A lease owned by a dead pid must not render as a running agent
    (it did, for 8 days)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="main",
                         lean_path="Problems/p/proofs/main.lean",
                         statement="True", origin="root")
    db.enqueue(conn, kind="Backward", target_id=str(gid),
               target_kind="Goal", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 99999")  # dead owner
    conn.commit()
    conn.close()

    c = _client(workspace)
    # no daemon: the stale lease is residue — zero in flight, no pulse
    rows = {p["name"]: p for p in
            c.get("/api/problems").json()["problems"]}
    assert rows["p"]["in_flight"] == 0
    assert all(not g["in_flight"]
               for g in c.get("/api/problems/p").json()["goals"])
    # live daemon owning the lease: it IS live work again
    _fake_daemon(monkeypatch, pid=99999, scope="p")
    rows2 = {p["name"]: p for p in
             c.get("/api/problems").json()["problems"]}
    assert rows2["p"]["in_flight"] == 1
    assert any(g["in_flight"]
               for g in c.get("/api/problems/p").json()["goals"])


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
    (proofs / "main.lean").write_text(
        "import Mathlib\n\ntheorem main : True := trivial",
        encoding="utf-8")

    c = _client(workspace)
    d = c.get("/api/problems/p").json()
    assert {g["slug"] for g in d["goals"]} == {"main", "lemma_a"}
    lemma = next(g for g in d["goals"] if g["slug"] == "lemma_a")
    assert lemma["dead_attempts"] == 1
    assert d["strategies"][0]["goal_id"] == gid
    # link_kind joined the PAYLOAD on 2026-08-26 (the column is v44):
    # the sky cannot tell a decomposition from a reuse without it, and
    # was drawing every reuse as a branch.
    assert d["strategy_edges"][0] == {
        "strategy_id": sid, "subgoal_id": sub, "position": 0,
        "link_kind": "minted"}
    assert d["decisions"][0]["decision_kind"] == "Noop"
    assert d["proof_files"] == ["main.lean"]

    g = c.get(f"/api/problems/p/goals/{sub}").json()
    assert g["dead_attempts"][0]["failure_reason"] == "agent_timeout"
    # declaration source: the proof file minus its import prelude;
    # missing file → null (statement fallback is the client's)
    gm = c.get(f"/api/problems/p/goals/{gid}").json()
    assert gm["proof_text"] == "theorem main : True := trivial"
    assert g["proof_text"] is None

    assert c.get("/api/problems/nope").status_code == 404


def test_cited_subgoal_is_a_reuse_not_a_branch(workspace: Path) -> None:
    """v44 `link_kind` reaches the read side (2026-08-26).

    A strategy's subgoal list holds two different things: goals the
    route CREATED (`minted`) and goals it merely reaches for
    (`cited`). Flattened, a lemma seven routes cite grew seven
    decomposition limbs on the sky and was dragged below all seven
    citers by the layering pass — and the route panel credited each
    citer with subgoals it never made. Worse, the group-attribution
    walk treated a citer as the lemma's PARENT, so a reused goal could
    inherit the wrong discussion group.
    """
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="main",
                         lean_path="Problems/p/proofs/main.lean",
                         statement="True", origin="root")
    minted = db.insert_goal(conn, problem="p", slug="lemma_minted",
                            lean_path="Problems/p/proofs/lemma_minted.lean",
                            statement="1 = 1", origin="backward")
    other = db.insert_goal(conn, problem="p", slug="other",
                           lean_path="Problems/p/proofs/other.lean",
                           statement="2 = 2", origin="backward")
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at) VALUES (?, 'x', 'proposed', 'test', ?)", (gid, ts))
    s_mint = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at) VALUES (?, 'y', 'proposed', 'test', ?)", (other, ts))
    s_cite = int(cur.lastrowid)
    db.link_subgoal(conn, strategy_id=s_mint, subgoal_id=minted,
                    position=0)
    db.link_subgoal(conn, strategy_id=s_mint, subgoal_id=other,
                    position=1)
    # `other`'s route does not decompose: it reaches for the lemma the
    # first route minted
    db.link_subgoal(conn, strategy_id=s_cite, subgoal_id=minted,
                    position=0, link_kind="cited")
    conn.commit()
    conn.close()

    c = _client(workspace)
    d = c.get("/api/problems/p").json()
    kinds = {(e["strategy_id"], e["subgoal_id"]): e["link_kind"]
             for e in d["strategy_edges"]}
    assert kinds[(s_mint, minted)] == "minted"
    assert kinds[(s_cite, minted)] == "cited"

    # the citing route's own record names the reuse as a reuse
    sd = c.get(f"/api/problems/p/strategies/{s_cite}").json()
    assert [(x["slug"], x["reused"]) for x in sd["subgoals"]] == [
        ("lemma_minted", True)]
    # and the minting route does not call its own children reused
    sm = c.get(f"/api/problems/p/strategies/{s_mint}").json()
    assert all(not x["reused"] for x in sm["subgoals"])

    # the goal panel's route list, same distinction
    g = c.get(f"/api/problems/p/goals/{other}").json()
    route = next(s for s in g["strategies"] if s["id"] == s_cite)
    assert [x["reused"] for x in route["subgoals"]] == [True]
    assert c.get("/api/problems/p/goals/99999").status_code == 404


def test_goal_locate_resolves_a_bare_goal_id(workspace: Path) -> None:
    """Prose across the reading layer names goals as `g<id>` and nothing
    else — no problem, no group. `locate` turns that id into a link
    target (HID §3.4); an id nobody minted is a 404, not an empty page."""
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    top = _groups.ensure_top_group(conn, "p", charter="# c")
    gid = db.insert_goal(conn, problem="p", slug="lemma_a",
                         lean_path="Problems/p/proofs/lemma_a.lean",
                         statement="1 = 1", origin="backward")
    db.update_goal_status(conn, gid, "attempting")
    conn.commit()
    conn.close()
    c = _client(workspace)
    assert c.get(f"/api/goals/{gid}/locate").json() == {
        "id": gid, "problem": "p", "slug": "lemma_a",
        "status": "attempting", "group_id": top}
    assert c.get("/api/goals/99999/locate").status_code == 404


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

def _charter_of(workspace: Path, problem: str = "p") -> str:
    conn = db.connect(workspace / "asterism.db")
    try:
        row = conn.execute(
            "SELECT charter FROM groups WHERE problem = ?"
            " AND parent_group_id IS NULL", (problem,)).fetchone()
        return "" if row is None else str(row["charter"])
    finally:
        conn.close()


def _amend_fixture(workspace: Path) -> tuple[int, Path]:
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    _groups.ensure_top_group(conn, "p", charter="# old")
    did = _add_decision(
        conn, "p", kind="RequestUserAmend", outcome="awaiting_human",
        payload={"file": "charter",
                 "proposed_body": "# proposed\nnew content\n",
                 "question": "apply this?"},
        reason="needs a stronger hypothesis")
    conn.close()
    pdir = workspace / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / ".proposed_charter").write_text(
        "# proposed\nnew content\n", encoding="utf-8")
    return did, pdir


def test_inbox_lists_amend_with_both_bodies(workspace: Path) -> None:
    _amend_fixture(workspace)
    box = _client(workspace).get("/api/inbox").json()
    assert len(box["amends"]) == 1
    a = box["amends"][0]
    assert a["problem"] == "p"
    assert a["file"] == "charter"
    assert a["proposed_body"].startswith("# proposed")
    # the side-by-side diff needs the CURRENT goal text — for the
    # DB-resident charter that is the top group's charter row
    assert a["current_body"] == "# old"
    assert a["question"] == "apply this?"
    meta = _client(workspace).get("/api/meta").json()
    assert meta["inbox_count"] == 1


def _amend_row(workspace: Path, payload: dict) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    _add_decision(conn, "p", kind="RequestUserAmend",
                  outcome="awaiting_human", payload=payload)
    conn.close()


def test_inbox_amend_title_comes_from_the_decision_payload(
        workspace: Path) -> None:
    """The reader's list needs one line naming the ask. A `title` the
    Strategist wrote in decision.json rides the payload the parser built
    (HID §3.4) — nothing between it and the inbox drops the field."""
    from Tooling.pipeline.strategist.model import parse_decision
    d, err = parse_decision(json.dumps({
        "kind": "RequestUserAmend", "problem": "p", "file": "charter",
        "proposed_body": "# proposed\n", "question": "apply this?",
        "title": "Charter omits the n = 0 case"}))
    assert err == "" and d is not None
    _amend_row(workspace, d.payload)
    a = _client(workspace).get("/api/inbox").json()["amends"][0]
    assert a["title"] == "Charter omits the n = 0 case"


def test_inbox_amend_title_falls_back_to_the_question(
        workspace: Path) -> None:
    """Absent (every row written before the field existed), the question's
    FIRST line stands in, capped at 80 chars — a list row is one line, and
    a question is a paragraph."""
    _amend_row(workspace, {"file": "charter", "proposed_body": "# proposed\n",
                           "question": "Q" * 100 + "\nand the reasoning\n"})
    a = _client(workspace).get("/api/inbox").json()["amends"][0]
    assert a["title"] == "Q" * 80


def test_amend_accept_writes_charter_and_resumes(workspace: Path) -> None:
    did, pdir = _amend_fixture(workspace)
    c = _client(workspace)
    r = c.post(f"/api/inbox/amend/{did}/resolve",
               json={"action": "accept"})
    assert r.status_code == 200
    # accept lands in the DB (top group charter), not in any file
    assert _charter_of(workspace) == "# proposed\nnew content"
    assert not (pdir / ".proposed_charter").exists()
    conn = db.connect(workspace / "asterism.db")
    row = conn.execute("SELECT outcome FROM strategist_decisions"
                       " WHERE id = ?", (did,)).fetchone()
    assert row["outcome"] == "accepted"
    # the sanctioned change moved the baseline pin
    hist = conn.execute(
        "SELECT source FROM user_file_history WHERE problem = 'p'"
        " AND file = 'charter' ORDER BY id DESC LIMIT 1").fetchone()
    assert hist is not None and hist["source"] == "repin"
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
    assert _charter_of(workspace) == "# operator-edited"


def test_amend_reject_leaves_charter_untouched(workspace: Path) -> None:
    did, pdir = _amend_fixture(workspace)
    r = _client(workspace).post(
        f"/api/inbox/amend/{did}/resolve",
        json={"action": "reject", "reason": "wrong direction"})
    assert r.status_code == 200
    assert _charter_of(workspace) == "# old"
    assert not (pdir / ".proposed_charter").exists()
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
    from Tooling.state import settings as _settings
    conn = _open_db(workspace)
    _add_problem(conn, "p", ingest_signoff_pending=1, ingested_at=db.now())
    # opted-in problem: approval must enqueue the harvest
    _settings.write(conn, "p", "library", True)
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


def test_approve_ingest_carries_the_library_decision(
        workspace: Path, monkeypatch) -> None:
    """The Library decision is made AT SIGN-OFF (owner: a human signs,
    nothing is harvested automatically): approve {library: false}
    writes the flag through the settings chokepoint before approving;
    a bodyless approve keeps the standing flag (legacy callers)."""
    from Tooling.state import settings as _settings
    conn = _open_db(workspace)
    _add_problem(conn, "p", ingest_signoff_pending=1, ingested_at=db.now())
    _settings.write(conn, "p", "library", True)
    conn.commit()
    conn.close()
    monkeypatch.chdir(workspace)
    c = _client(workspace)
    r = c.post("/api/problems/p/approve-ingest", json={"library": False})
    assert r.status_code == 200
    assert r.json()["library"] is False
    conn = db.connect(workspace / "asterism.db")
    assert _settings.read(conn, "p")["library"] is False
    assert not db.problem_ingest_signoff_pending(conn, "p")
    # signing with library:false must not start a harvest (2026-07-18:
    # the old unconditional enqueue was a BUG3-class gate bypass)
    assert not db.is_in_queue(conn, target_id="p", kind="Librarian")
    conn.close()


def test_delete_problem_guards_and_deletes(workspace: Path,
                                           monkeypatch) -> None:
    """Deletion is chokepoint-guarded: bridged problems 409 (their
    chapter imports the proofs), and a clean delete removes the DB
    row AND the directory in one act (rule 10)."""
    from Tooling.state import db as _db
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    _add_problem(conn, "q")
    _db.mark_library_bridged(conn, "q")
    conn.commit()
    conn.close()
    pdir = workspace / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "problem.json").write_text(
        '{"problem": "p", "charter": "x"}', encoding="utf-8")
    monkeypatch.chdir(workspace)
    c = _client(workspace)
    # bridged refuses
    r = c.post("/api/problems/q/delete")
    assert r.status_code == 409
    assert "Library" in r.json()["detail"]
    # unknown 404s
    assert c.post("/api/problems/nope/delete").status_code == 404
    # clean delete: row gone, dir gone
    r = c.post("/api/problems/p/delete")
    assert r.status_code == 200
    assert not pdir.exists()
    conn = _db.connect(workspace / "asterism.db")
    assert conn.execute(
        "SELECT 1 FROM problems WHERE name='p'").fetchone() is None
    conn.close()


def test_approve_harvest_starts_the_run(workspace: Path,
                                        monkeypatch) -> None:
    """'Harvest to Library' harvests NOW (owner call: the click IS the
    go signal) — approve {library: true} best-effort starts a scoped
    once-run; a busy engine must not undo the approval."""
    import Tooling.core.cli as _cli
    calls: list = []
    monkeypatch.setattr(
        _cli, "daemon_start",
        lambda ws, scope=None, once=False: (calls.append((scope, once))
                                            or (0, "started pid 1")))
    conn = _open_db(workspace)
    _add_problem(conn, "p", ingest_signoff_pending=1, ingested_at=db.now())
    conn.close()
    monkeypatch.chdir(workspace)
    r = _client(workspace).post("/api/problems/p/approve-ingest",
                                json={"library": True})
    assert r.status_code == 200
    assert r.json()["harvest_run"] == "started"
    assert calls == [("p", True)]


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


def test_telemetry_usage_windows_to_running_daemon(
        workspace: Path, monkeypatch) -> None:
    """"usage — this run" must BE this run: with a live daemon the
    window starts at its start time; idle, it's the all-time ledger,
    labelled as such (the header used to say "this run" over the
    all-time aggregate)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    for ts in ("2020-01-01T00:00:00+00:00", db.now()):
        conn.execute(
            "INSERT INTO spawn_usage (pipeline_id, kind, problem,"
            " input_tokens, output_tokens, turns, wall_sec, ts)"
            " VALUES ('pl', 'Forward', 'p', 10, 5, 1, 2.5, ?)", (ts,))
    conn.commit()
    conn.close()

    c = _client(workspace)
    r = c.get("/api/telemetry/usage").json()
    assert r["window"] == "all"
    assert r["problems"][0]["spawns"] == 2

    _fake_daemon(monkeypatch, scope="p",
                 started_at="2025-01-01T00:00:00+00:00")
    r2 = c.get("/api/telemetry/usage").json()
    assert r2["window"] == "run"
    assert r2["since"] == "2025-01-01T00:00:00+00:00"
    assert r2["problems"][0]["spawns"] == 1


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


def test_library_chapter_reads_curated_modules(workspace: Path) -> None:
    """GET /api/library/{p}: modules in import order, decls in source
    order with docstrings from the curated file, deliverable flag from
    the goal side. 404 for unbridged problems."""
    conn = _open_db(workspace)
    _add_problem(conn, "p", library_bridged_at=db.now())
    gid = db.insert_goal(conn, problem="p", slug="main_thm",
                         lean_path="Problems/p/proofs/main_thm.lean",
                         statement="True", origin="root", status="proved")
    db.mark_deliverable(conn, gid, True)
    ts = db.now()
    for slug, tf, tn, sig, kind in [
            ("main_thm", "Library/X/Main.lean", "Lib.X.Main.mainThm",
             "sig", "theorem"),
            ("helper", "Library/X/Main.lean", "Lib.X.Main.helper",
             "sig", "theorem"),
            # pre-oracle harvest row: no stored signature/kind — the
            # curated source text stands in (display fallback)
            ("base_def", "Library/X/Defs.lean", "Lib.X.Defs.baseDef",
             None, None)]:
        conn.execute(
            "INSERT INTO library_decls (problem, slug, lifecycle,"
            " target_file, target_name, signature, decl_kind, created_at,"
            " updated_at) VALUES ('p', ?, 'cleaned', ?, ?, ?, ?, ?, ?)",
            (slug, tf, tn, sig, kind, ts, ts))
    conn.commit()
    conn.close()
    (workspace / "Library" / "X").mkdir(parents=True)
    (workspace / "Library" / "X" / "Defs.lean").write_text(
        "import Mathlib\n/-!\n# Base defs\nThe vocabulary.\n-/\n"
        "/-- The base object. -/\ndef baseDef : Nat := 0\n",
        encoding="utf-8")
    (workspace / "Library" / "X" / "Main.lean").write_text(
        "import Library.X.Defs\n/-!\n# Main\n-/\n"
        "/-- A helper step. -/\ntheorem helper : baseDef = 0 := rfl\n"
        "/-- The main result. -/\n@[simp]\ntheorem mainThm : True := trivial\n",
        encoding="utf-8")

    c = _client(workspace)
    ch = c.get("/api/library/p").json()
    # Defs precedes Main (Main imports it), regardless of path order
    assert [f["path"] for f in ch["files"]] == [
        "Library/X/Defs.lean", "Library/X/Main.lean"]
    assert "vocabulary" in ch["files"][0]["module_doc"]
    main = ch["files"][1]
    # source order, not DB order: helper is declared first
    assert [d["slug"] for d in main["decls"]] == ["helper", "main_thm"]
    # docstring attaches across the @[simp] attribute line
    assert main["decls"][1]["doc"] == "The main result."
    assert main["decls"][1]["is_deliverable"] is True
    assert main["decls"][0]["is_deliverable"] is False
    # stored oracle signature wins; a pre-oracle row falls back to the
    # curated source header (statement, no proof body)
    assert main["decls"][0]["signature"] == "sig"
    base = ch["files"][0]["decls"][0]
    assert base["signature"] == "def baseDef : Nat"
    assert base["decl_kind"] == "def"
    # keystone weight: baseDef is reached for from Main.lean; helper
    # is not used outside its own module
    assert base["used_by"] == 1
    assert main["decls"][0]["used_by"] == 0
    # the file-level sky: Main imports Defs, within this problem
    assert main["imports_within"] == ["Library/X/Defs.lean"]
    assert ch["files"][0]["imports_within"] == []
    assert c.get("/api/library/nope").status_code == 404


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

def test_problem_detail_citation_edges(workspace: Path) -> None:
    """Proof-file `import Problems.<p>.proofs.L_<slug>` lines surface
    as citation_edges when the cited NAME is used in the citing body
    (visualization truth: what the tree views under-report — a forward
    lemma cited by a node has real structure). An import alone is NOT
    a citation: Backward inherits ancestor preambles, so dead imports
    ride down whole subtrees (slc drew a 28-edge super-hub of
    nothing). Instance bricks stay import-evidenced — typeclass
    resolution uses them namelessly."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    a = db.insert_goal(conn, problem="p", slug="lemma_a",
                       lean_path="Problems/p/proofs/L_lemma_a.lean",
                       statement="True", origin="forward")
    b = db.insert_goal(conn, problem="p", slug="main_thm",
                       lean_path="Problems/p/proofs/L_main_thm.lean",
                       statement="True", origin="backward")
    stmt = db.insert_goal(conn, problem="p", slug="stmt_def",
                          lean_path="Problems/p/proofs/L_stmt_def.lean",
                          statement="Prop", origin="forward", kind="def")
    inst = db.insert_goal(conn, problem="p", slug="inst_brick",
                          lean_path="Problems/p/proofs/L_inst_brick.lean",
                          statement="True", origin="forward",
                          kind="instance")
    conn.commit()
    conn.close()
    pdir = workspace / "Problems" / "p" / "proofs"
    pdir.mkdir(parents=True)
    for slug in ("lemma_a", "stmt_def", "inst_brick"):
        (pdir / f"L_{slug}.lean").write_text(
            f"import Mathlib\ntheorem {slug} : True := trivial\n",
            encoding="utf-8")
    (pdir / "L_main_thm.lean").write_text(
        "import Mathlib\n"
        "import Problems.p.proofs.L_lemma_a\n"
        "import Problems.p.proofs.L_stmt_def\n"   # inherited, never used
        "import Problems.p.proofs.L_inst_brick\n"  # instance: nameless use
        "namespace Problems.p.stmt_def\n"
        "-- rationale prose naming stmt_def must not count as a use\n"
        "theorem main_thm : True := lemma_a\n"
        "-- a qualified path THROUGH the name is a prefix, not a use:\n"
        "example : True := Problems.p.stmt_def.other\n"
        "end Problems.p.stmt_def\n", encoding="utf-8")
    d = _client(workspace).get("/api/problems/p").json()
    assert {"from": a, "to": b} in d["citation_edges"]
    # the unused inherited import draws nothing — no super-hub
    assert {"from": stmt, "to": b} not in d["citation_edges"]
    # the instance brick keeps its import-evidenced edge
    assert {"from": inst, "to": b} in d["citation_edges"]
    # self-imports / unknown slugs never edge
    assert all(e["from"] != e["to"] for e in d["citation_edges"])


def test_goal_disproof_linkage(workspace: Path) -> None:
    """An AttemptDisproof decision's mechanical linkage (target_id=P,
    produced_goal_id=¬P) surfaces on the ¬P goal as disproof_of in both
    problem_detail and goal_detail — a proved negation must not dress
    as ordinary success anywhere it is read."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    p_goal = db.insert_goal(conn, problem="p", slug="claim_p",
                            lean_path="Problems/p/proofs/L_claim_p.lean",
                            statement="P", origin="forward")
    neg = db.insert_goal(conn, problem="p", slug="not_claim_p",
                         lean_path="Problems/p/proofs/L_not_claim_p.lean",
                         statement="¬ P", origin="forward")
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, produced_goal_id,"
        " brief, reason, payload, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'AttemptDisproof', ?, ?, 'b', 'r',"
        " '{}', ?, ?)", (p_goal, neg, db.now(), db.now()))
    conn.commit()
    conn.close()
    c = _client(workspace)
    goals = {g["slug"]: g for g in c.get("/api/problems/p").json()["goals"]}
    assert goals["not_claim_p"]["disproof_of"] == {
        "id": p_goal, "slug": "claim_p"}
    assert goals["claim_p"]["disproof_of"] is None
    gd = c.get(f"/api/problems/p/goals/{neg}").json()
    assert gd["disproof_of"] == {"id": p_goal, "slug": "claim_p"}


def test_citation_edges_from_strategy_scratch(workspace: Path) -> None:
    """A Backward assembly's citations live in the strategy's scratch
    patch, not in any goal's own L_ file. A succeeded strategy's
    non-child imports are its goal's citations; child imports are the
    hierarchy (already bundle arms) and never double as citations;
    dead strategies' imports are dead attempts, not story."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    parent = db.insert_goal(conn, problem="p", slug="parent_thm",
                            lean_path="Problems/p/proofs/L_parent_thm.lean",
                            statement="True", origin="backward")
    child = db.insert_goal(conn, problem="p", slug="child_lemma",
                           lean_path="Problems/p/proofs/L_child_lemma.lean",
                           statement="True", origin="backward")
    brick = db.insert_goal(conn, problem="p", slug="forward_brick",
                           lean_path="Problems/p/proofs/L_forward_brick.lean",
                           statement="True", origin="forward")
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at, scratch_path) VALUES (?, 'x', 'succeeded', 'test', ?,"
        " 'Problems/p/proofs/_strategy_s1.lean')", (parent, ts))
    sid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, 0)", (sid, child))
    conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at, scratch_path) VALUES (?, 'x', 'dead', 'test', ?,"
        " 'Problems/p/proofs/_strategy_s2.lean')", (parent, ts))
    conn.commit()
    conn.close()
    pdir = workspace / "Problems" / "p" / "proofs"
    pdir.mkdir(parents=True)
    for slug in ("parent_thm", "child_lemma", "forward_brick"):
        (pdir / f"L_{slug}.lean").write_text(
            f"import Mathlib\ntheorem {slug} : True := trivial\n",
            encoding="utf-8")
    patch = ("import Mathlib\n"
             "import Problems.p.proofs.L_child_lemma\n"
             "import Problems.p.proofs.L_forward_brick\n"
             "theorem parent_thm : True := forward_brick child_lemma\n")
    (pdir / "_strategy_s1.lean").write_text(patch, encoding="utf-8")
    # the dead attempt cites a different brick — must never surface
    (pdir / "_strategy_s2.lean").write_text(
        patch.replace("L_forward_brick", "L_child_lemma"),
        encoding="utf-8")
    c = _client(workspace)
    edges = c.get("/api/problems/p").json()["citation_edges"]
    assert {"from": brick, "to": parent} in edges  # the forward brick links
    assert {"from": child, "to": parent} not in edges  # hierarchy, not cite
    # the goal's source is the winning route's scratch (the real
    # proof), not its own delegate file
    gp = c.get(f"/api/problems/p/goals/{parent}").json()
    assert gp["proof_text"].startswith("theorem parent_thm")


def test_goal_source_shows_the_working_text_not_the_stub(
        workspace: Path) -> None:
    """A node's own file is `:= by sorry` for its whole working life —
    the decomposition lands in the ROUTE's file and a live attempt
    exists only in a workarea. Clicking the star must show that work
    (owner, 2026-08-01), labelled with what it is: an open route's
    skeleton, an attempt mid-write, or the untouched statement."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="split_me",
                         lean_path="Problems/p/proofs/L_split_me.lean",
                         statement="True", origin="backward")
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at, scratch_path) VALUES (?, 'x', 'proposed', 'test', ?,"
        " 'Problems/p/proofs/_strategy_s1.lean')", (gid, ts))
    sid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    pdir = workspace / "Problems" / "p" / "proofs"
    pdir.mkdir(parents=True)
    (pdir / "L_split_me.lean").write_text(
        "import Mathlib\ntheorem split_me : True := by sorry\n",
        encoding="utf-8")
    c = _client(workspace)

    # no route file on disk yet → the honest fallback is its own file
    g = c.get(f"/api/problems/p/goals/{gid}").json()
    assert g["source_state"] == "own_file"
    assert "sorry" in g["proof_text"]

    # the open route's skeleton IS how the goal is split right now
    (pdir / "_strategy_s1.lean").write_text(
        "import Mathlib\ntheorem split_me : True := by\n"
        "  have step : True := piece_one\n  exact step\n", encoding="utf-8")
    g = c.get(f"/api/problems/p/goals/{gid}").json()
    assert g["source_state"] == "open_route"
    assert g["source_strategy_id"] == sid
    assert "have step" in g["proof_text"]

    # an agent writing right now outranks both — its draft is the only
    # place that work exists until commit
    wa = workspace / ".attempts" / "pid1"
    wa.mkdir(parents=True)
    (wa / "Context.md").write_text("# Context for goal split_me\n",
                                   encoding="utf-8")
    (wa / "patch.lean").write_text(
        "import Mathlib\ntheorem split_me : True := by\n"
        "  exact trivial_in_progress\n", encoding="utf-8")
    g = c.get(f"/api/problems/p/goals/{gid}").json()
    assert g["source_state"] == "in_flight"
    assert g["source_path"] == ".attempts/pid1/patch.lean"
    assert "trivial_in_progress" in g["proof_text"]

    # a finished route still wins the label it earned
    conn = _open_db(workspace)
    conn.execute("UPDATE strategies SET status = 'succeeded' WHERE id = ?",
                 (sid,))
    conn.commit()
    conn.close()
    (pdir / "_strategy_s1.lean").touch()  # landed after the draft
    g = c.get(f"/api/problems/p/goals/{gid}").json()
    assert g["source_state"] == "winning_route"


def test_papers_bookshelf_flow(workspace: Path) -> None:
    """Top-level bookshelf: browser upload (raw bytes, content-hash
    idempotent), list with bindings, read text + original, delete
    guarded by citations (unbind first)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    conn.close()
    c = _client(workspace)
    assert c.get("/api/papers").json() == {"papers": []}
    body = b"# Paper\n\nsome text"
    r = c.post("/api/papers/upload", params={"filename": "notes.md"},
               content=body)
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["already_shelved"] is False
    again = c.post("/api/papers/upload", params={"filename": "other.md"},
                   content=body).json()
    assert again["id"] == pid and again["already_shelved"] is True
    papers = c.get("/api/papers").json()["papers"]
    assert [p["id"] for p in papers] == [pid]
    assert papers[0]["bound"] == []
    assert "some text" in c.get(f"/api/papers/{pid}/text").json()["text"]
    assert c.get(f"/api/papers/{pid}/file").status_code == 200
    # server owns format/emptiness validation (one validator, one wording)
    assert c.post("/api/papers/upload", params={"filename": "x.docx"},
                  content=b"zz").status_code == 422
    assert c.post("/api/papers/upload", params={"filename": "empty.md"},
                  content=b"").status_code == 422

    assert c.post("/api/problems/p/papers",
                  json={"paper_id": pid}).status_code == 200
    assert c.post("/api/problems/p/papers",
                  json={"paper_id": "unshelved"}).status_code == 404
    assert c.get("/api/papers").json()["papers"][0]["bound"] == [
        {"problem": "p", "origin": "user"}]
    mine = c.get("/api/problems/p/papers").json()["papers"]
    assert mine[0]["id"] == pid and mine[0]["origin"] == "user"
    # cited → delete refused; unbind → delete ok
    assert c.delete(f"/api/papers/{pid}").status_code == 409
    assert c.delete(f"/api/problems/p/papers/{pid}").status_code == 200
    assert c.delete(f"/api/problems/p/papers/{pid}").status_code == 404
    assert c.delete(f"/api/papers/{pid}").status_code == 200
    assert c.get("/api/papers").json() == {"papers": []}


def test_paper_upload_provenance_and_filename_hygiene(
        workspace: Path) -> None:
    """Browser uploads record added_by='user' (the shelf's provenance
    tag — Scholar fetches record 'fetched') and the wire filename is
    reduced to a safe basename: the shelf must never mirror client
    paths, and identity never depends on the name anyway."""
    c = _client(workspace)
    r = c.post("/api/papers/upload",
               params={"filename": "C:\\Users\\me\\Desktop\\no:tes.md"},
               content=b"hello world")
    assert r.status_code == 200
    assert r.json()["source_name"] == "no_tes.md"
    got = c.get("/api/papers").json()["papers"][0]
    assert got["added_by"] == "user"
    assert c.post("/api/papers/upload", params={"filename": "..."},
                  content=b"x").status_code == 422


def test_paper_rename_display_title(workspace: Path) -> None:
    """The display title is owner-editable and display-ONLY: identity
    (content hash) and the source filename survive; empty clears back
    to the filename; old meta.json files without the field keep
    loading (dataclass default)."""
    c = _client(workspace)
    pid = c.post("/api/papers/upload", params={"filename": "notes.md"},
                 content=b"# Paper\n\nsome text").json()["id"]
    assert c.get("/api/papers").json()["papers"][0]["title"] is None
    r = c.post(f"/api/papers/{pid}/rename",
               json={"title": "Residues and their applications"})
    assert r.status_code == 200
    got = c.get("/api/papers").json()["papers"][0]
    assert got["title"] == "Residues and their applications"
    assert got["source_name"] == "notes.md" and got["id"] == pid
    # empty title clears back to the filename standing in
    assert c.post(f"/api/papers/{pid}/rename",
                  json={"title": "  "}).status_code == 200
    assert c.get("/api/papers").json()["papers"][0]["title"] is None
    assert c.post("/api/papers/nope/rename",
                  json={"title": "x"}).status_code == 404


def test_create_settings_and_papers_are_authoritative(
        workspace: Path) -> None:
    """Creation-time settings land in the DB via the chokepoint —
    explicit form input must win over lazy migration — and checked
    papers bind with origin='user'."""
    _open_db(workspace).close()
    c = _client(workspace)
    pid = c.post("/api/papers/upload", params={"filename": "ref.md"},
                 content=b"# Ref\n\nbody").json()["id"]
    r = c.post("/api/problems/create", json={
        "name": "Test.cite", "charter": "prove the thing",
        "settings": {"forbidden_lemmas": ["bad*"], "library": False},
        "papers": [pid]})
    assert r.status_code == 200, r.json()
    got = c.get("/api/problems/Test.cite/intent").json()["settings"]
    assert got["forbidden_lemmas"] == ["bad*"]
    assert got["library"] is False
    bound = c.get("/api/problems/Test.cite/papers").json()["papers"]
    assert [(b["id"], b["origin"]) for b in bound] == [(pid, "user")]


def test_daemon_status_endpoint(workspace: Path) -> None:
    r = _client(workspace).get("/api/daemon")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False
    assert body["stopping"] is False
    assert body["started_at"] is None


def test_daemon_start_requires_exact_known_scope(
        workspace: Path, monkeypatch) -> None:
    """The UI path runs ONE existing problem: empty scope is a 400
    (workspace-wide runs are CLI-only deliberate acts), a typo is a 404
    — never a silent `--all-problems` dispatch."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    conn.close()
    c = _client(workspace)
    assert c.post("/api/daemon/start", json={}).status_code == 400
    assert c.post("/api/daemon/start",
                  json={"scope": "  "}).status_code == 400
    assert c.post("/api/daemon/start",
                  json={"scope": "no_such"}).status_code == 404
    import Tooling.core.cli as _cli
    seen = {}

    def fake_start(ws, *, scope=None, once=False):  # noqa: ANN001
        seen["scope"] = scope
        return 0, f"started daemon pid 1; scope {scope}"
    monkeypatch.setattr(_cli, "daemon_start", fake_start)
    r = c.post("/api/daemon/start", json={"scope": "p"})
    assert r.status_code == 200
    assert seen["scope"] == "p"


# ---------------------------------------------------------------------
# problem authoring (POST /api/problems/create)
# ---------------------------------------------------------------------

_CHARTER = ("# Test.ui_created — a UI-authored problem\n\n"
            "## Statement\n\nProve something small.\n")


def test_create_problem_pure_nl(workspace: Path) -> None:
    c = _client(workspace)
    r = c.post("/api/problems/create",
               json={"name": "Test.ui_created", "charter": _CHARTER})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["problem"] == "Test.ui_created"
    assert "pure-NL" in body["message"]
    pdir = workspace / "Problems" / "Test" / "ui_created"
    seed = json.loads((pdir / "problem.json").read_text(encoding="utf-8"))
    assert seed["problem"] == "Test.ui_created"
    assert seed["charter"] == _CHARTER.strip()
    assert (pdir / "proofs").is_dir()
    conn = db.connect(workspace / "asterism.db")
    row = conn.execute("SELECT 1 FROM problems WHERE name = ?",
                       ("Test.ui_created",)).fetchone()
    charter = conn.execute(
        "SELECT charter FROM groups WHERE problem = ?"
        " AND parent_group_id IS NULL", ("Test.ui_created",)).fetchone()
    conn.close()
    assert row is not None
    assert charter is not None and charter["charter"] == _CHARTER.strip()
    # visible on the board immediately
    names = [p["name"] for p in c.get("/api/problems").json()["problems"]]
    assert "Test.ui_created" in names


def test_create_problem_duplicate_409(workspace: Path) -> None:
    c = _client(workspace)
    assert c.post("/api/problems/create",
                  json={"name": "Test.dup", "charter": _CHARTER
                        }).status_code == 200
    r = c.post("/api/problems/create",
               json={"name": "Test.dup", "charter": _CHARTER})
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


def test_create_problem_bad_name_422(workspace: Path) -> None:
    c = _client(workspace)
    for bad in ("", "1starts_with_digit", "has space", "trailing.", "a..b",
                "semi;colon"):
        r = c.post("/api/problems/create",
                   json={"name": bad, "charter": _CHARTER})
        assert r.status_code == 422, bad
    assert not (workspace / "Problems" / "has space").exists()


def test_create_problem_empty_charter_422(workspace: Path) -> None:
    r = _client(workspace).post(
        "/api/problems/create",
        json={"name": "Test.empty", "charter": "   \n"})
    assert r.status_code == 422
    assert not (workspace / "Problems" / "Test" / "empty").exists()


def test_create_problem_init_failure_rolls_back(
        workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from Tooling.core import cli as _cli
    monkeypatch.setattr(_cli, "init_problem",
                        lambda ws, name, **kw: (1, "FAIL: stubbed"))
    r = _client(workspace).post(
        "/api/problems/create",
        json={"name": "Test.rollback", "charter": _CHARTER})
    assert r.status_code == 422
    assert "stubbed" in r.json()["detail"]
    # the created directory is rolled back so a retry can succeed
    assert not (workspace / "Problems" / "Test" / "rollback").exists()


# ---------------------------------------------------------------------
# intent read/update + settings create + config
# ---------------------------------------------------------------------

def test_create_settings_land_in_db_and_seed_mirror(workspace: Path) -> None:
    """Explicit creation-time settings go straight to the DB (where
    every gate reads them) AND the settings chokepoint mirrors them
    into the durable problem.json seed, so reset/re-init restores
    exactly what the user authored."""
    from Tooling.state import intent as _intent
    from Tooling.state import settings as _settings
    c = _client(workspace)
    r = c.post("/api/problems/create", json={
        "name": "Test.structured",
        "charter": "# Test.structured\n\n## Statement\n\nProve it.\n",
        "settings": {"forbidden_lemmas": ["sperner*"], "library": True},
    })
    assert r.status_code == 200, r.text
    conn = db.connect(workspace / "asterism.db")
    try:
        stored = _settings.read(conn, "Test.structured")
    finally:
        conn.close()
    assert stored["forbidden_lemmas"] == ["sperner*"]
    assert stored["library"] is True
    seed = _intent.read_seed(
        workspace / "Problems" / "Test" / "structured" / "problem.json")
    assert seed is not None
    assert "## Statement" in seed["charter"]
    assert seed["settings"]["forbidden_lemmas"] == ["sperner*"]
    assert seed["settings"]["library"] is True


def test_intent_get_and_update(workspace: Path) -> None:
    c = _client(workspace)
    c.post("/api/problems/create", json={
        "name": "Test.editme",
        "charter": "# Test.editme\n\nOld body.\n",
        "settings": {"library": False},
    })
    got = c.get("/api/problems/Test.editme/intent").json()
    assert got["settings"]["library"] is False
    assert "Old body." in got["charter"]
    assert got["word"] == ""
    assert got["pending_amend"] is False
    r = c.post("/api/problems/Test.editme/intent", json={
        "charter": "\n# Test.editme\n\nNew body.\n",
        "word": "stay on the analytic route",
        "settings": {"library": True, "forbidden_lemmas": ["kuhn*"]},
    })
    assert r.status_code == 200, r.text
    got2 = c.get("/api/problems/Test.editme/intent").json()
    assert got2["settings"]["library"] is True
    assert got2["settings"]["forbidden_lemmas"] == ["kuhn*"]
    assert "New body." in got2["charter"]
    assert got2["word"] == "stay on the analytic route"
    # the durable seed follows the DB write (the chokepoint mirrors it)
    seed = json.loads(
        (workspace / "Problems" / "Test" / "editme" /
         "problem.json").read_text(encoding="utf-8"))
    assert "New body." in seed["charter"]
    assert seed["word"] == "stay on the analytic route"


def test_review_get_enriches_vouch_signatures(workspace: Path) -> None:
    """The sign-off sheet carries what the human READS: every
    deliverable + anchor entry gets its declaration header from the
    proof file (goals.statement for a def is just the target sort);
    bare-name and record-shaped entries both normalize to records."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    db.insert_goal(conn, problem="p", slug="is_widget",
                   lean_path="Problems/p/proofs/L_is_widget.lean",
                   statement="Prop", origin="forward", status="proved")
    db.insert_goal(conn, problem="p", slug="widget_stable",
                   lean_path="Problems/p/proofs/L_widget_stable.lean",
                   statement="∀ w, is_widget w", origin="forward",
                   status="proved")
    db.set_review_snapshot(conn, "p", json.dumps({
        "deliverables": [{
            "fq": "Problems.p.widget_stable", "problem": "p",
            "slug": "widget_stable", "ok": True, "error": None,
            "kind": "theorem", "module": None, "paper": "",
            "folded": 0, "claims": [],
            # one record-shaped + one bare-name anchor
            "anchors": [{"kind": "def", "module": "m",
                         "name": "Problems.p.is_widget"},
                        "Problems.p.is_widget"],
        }],
        "union_count": 1}))
    conn.commit()
    conn.close()
    pdir = workspace / "Problems" / "p" / "proofs"
    pdir.mkdir(parents=True)
    (pdir / "L_is_widget.lean").write_text(
        "import Mathlib\n/-- A widget predicate. -/\n"
        "def is_widget (w : Nat) : Prop := w = w\n", encoding="utf-8")
    (pdir / "L_widget_stable.lean").write_text(
        "import Mathlib\ntheorem widget_stable : ∀ w, is_widget w := by\n"
        "  intro w; rfl\n", encoding="utf-8")

    d = _client(workspace).get("/api/problems/p/review").json()
    dv = d["deliverables"][0]
    # propositions: statement head only (the kernel owns the proof)
    assert dv["signature"] == "theorem widget_stable : ∀ w, is_widget w"
    assert all(isinstance(a, dict) for a in dv["anchors"])
    # def-kinds: FULL source incl. the := body — the construction IS
    # what the human vouches for (owner: type alone is unreadable)
    assert dv["anchors"][0]["signature"] == \
        "def is_widget (w : Nat) : Prop := w = w"
    assert dv["anchors"][1] == {
        "name": "Problems.p.is_widget",
        "signature": "def is_widget (w : Nat) : Prop := w = w"}


def test_intent_axiom_gate_locked_after_creation(workspace: Path) -> None:
    """Mutability inventory (owner, 2026-07-08): the axiom gate is
    creation-fixed — the gate re-reads it per validation, so a mid-life
    edit would re-tune soundness under live proofs. Same-value writes
    (the UI round-trips the whole settings object) still pass."""
    c = _client(workspace)
    c.post("/api/problems/create", json={
        "name": "Test.gate", "charter": "# Test.gate\n",
        "settings": {"axioms_whitelist": ["propext", "Quot.sound"]}})
    # widening → refused
    r = c.post("/api/problems/Test.gate/intent", json={
        "settings": {"axioms_whitelist":
                     ["propext", "Quot.sound", "Classical.choice"]}})
    assert r.status_code == 409
    assert "AXIOMS_LOCKED" in r.json()["detail"]
    # narrowing → refused too (the gate never changes, either way)
    r = c.post("/api/problems/Test.gate/intent", json={
        "settings": {"axioms_whitelist": ["propext"]}})
    assert r.status_code == 409
    # identical round-trip (order-insensitive) → fine
    r = c.post("/api/problems/Test.gate/intent", json={
        "settings": {"axioms_whitelist": ["Quot.sound", "propext"],
                     "forbidden_lemmas": ["kuhn*"]}})
    assert r.status_code == 200, r.text
    got = c.get("/api/problems/Test.gate/intent").json()["settings"]
    assert got["forbidden_lemmas"] == ["kuhn*"]


def test_intent_library_settles_after_bridge(workspace: Path) -> None:
    c = _client(workspace)
    c.post("/api/problems/create", json={
        "name": "Test.settled", "charter": "# Test.settled\n",
        "settings": {"library": True}})
    conn = _open_db(workspace)
    conn.execute("UPDATE problems SET library_bridged_at = ? WHERE name = ?",
                 (db.now(), "Test.settled"))
    conn.commit()
    conn.close()
    r = c.post("/api/problems/Test.settled/intent", json={
        "settings": {"library": False}})
    assert r.status_code == 409
    assert "LIBRARY_SETTLED" in r.json()["detail"]
    # same-value round-trip stays fine
    r = c.post("/api/problems/Test.settled/intent", json={
        "settings": {"library": True}})
    assert r.status_code == 200, r.text


def test_intent_charter_update_blocked_by_pending_amend(
        workspace: Path) -> None:
    c = _client(workspace)
    c.post("/api/problems/create", json={
        "name": "Test.locked", "charter": "# Test.locked\n"})
    conn = _open_db(workspace)
    _add_decision(conn, "Test.locked", kind="RequestUserAmend",
                  outcome="awaiting_human",
                  payload={"file": "charter"})
    conn.close()
    r = c.post("/api/problems/Test.locked/intent",
               json={"charter": "\n# clobber\n"})
    assert r.status_code == 409
    assert "Inbox" in r.json()["detail"]


def test_config_get_and_set(workspace: Path) -> None:
    c = _client(workspace)
    got = c.get("/api/config").json()["settings"]
    keys = {row["key"] for row in got}
    assert "strategist.model" in keys and "dispatch.pool" in keys
    # (scholar seat retired 2026-08-22 with the Scholar pipeline)
    assert "scholar.model" not in keys
    # .model keys carry dropdown choices (typo-proof select); the
    # resolved value is always a legal choice; bools render as a
    # true/false select reflecting the ENGINE default when unset
    # (quota_wait defaults OFF since 2026-07-18 — riding further quota
    # windows is opt-in); numeric knobs carry none
    by_key = {row["key"]: row for row in got}
    for k, row in by_key.items():
        if k.endswith(".model"):
            assert row["choices"], k
            if row["resolved"]:
                assert str(row["resolved"]) in row["choices"], k
        elif row["type"] == "bool":
            assert row["choices"] == ["true", "false"], k
            assert row["resolved"] in ("true", "false"), k
        elif k.endswith(".provider"):
            # writable, but NOT its own control: the model picker sets
            # it, because a seat's backend is implied by its model
            assert "claude" in row["choices"] and "codex" in row["choices"], k
            assert row["resolved"] in row["choices"], k
        else:
            assert "choices" not in row, k
    # a model picker offers ITS OWN SEAT's backend's names. A flat
    # claude-only list offered `claude-fable-5` for a codex seat, which
    # is the failure a select was introduced to prevent, one level up
    # (2026-08-14).
    # ONE picker: a model row carries every backend's names, GROUPED,
    # so choosing a model chooses the backend that runs it. Two controls
    # would let them disagree — `provider: codex` with `claude-sonnet-5`
    # is a run that dies at its first spawn (owner, 2026-08-14).
    for seat in ("formalizer", "strategist"):
        groups = by_key[f"{seat}.model"]["groups"]
        assert {g["provider"] for g in groups} >= {"claude", "codex"}
        # every name appears under exactly one backend, or "which one
        # runs this?" has no answer
        seen: dict = {}
        for g in groups:
            assert g["models"], g["provider"]
            assert g["source"] in ("probe", "declared")
            for m in g["models"]:
                assert m not in seen, (m, g["provider"], seen.get(m))
                seen[m] = g["provider"]
        # unset is a real state (the picker shows "not set — the
        # provider's default"); a SET value must be pickable, or the
        # control cannot show the current truth
        cur = by_key[f"{seat}.model"]["resolved"]
        if cur:
            assert str(cur) in seen
    assert by_key["dispatch.quota_wait"]["resolved"] == "false"
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


# ---------------------------------------------------------------------
# POST /api/lean/eval — the reader's Lean scratch pipeline
# ---------------------------------------------------------------------

def test_lean_eval_assemble_and_map() -> None:
    """Pure core: parts concatenate after the import preamble, and
    global diagnostic lines map back to part-local lines."""
    from Tooling.serve import lean_eval as le
    text, n_pre, spans = le._assemble(
        [("defs", "def a := 1\ndef b := 2"), ("root", "#check a")],
        imports=[])
    assert text.startswith("import Mathlib\n")          # auto-preamble
    assert n_pre == 1
    assert spans == [("defs", 2, 3), ("root", 4, 4)]
    mapped = le._map_diags(
        [{"line": 1, "col": 0, "severity": "error", "message": "bad import"},
         {"line": 3, "col": 4, "severity": "error", "message": "oops"},
         {"line": 4, "col": 0, "severity": "information", "message": "a : Nat"}],
        n_pre, spans)
    assert mapped["_preamble"][0]["message"] == "bad import"
    assert mapped["defs"] == [{"line": 2, "col": 4, "severity": "error",
                               "message": "oops"}]
    assert mapped["root"][0]["severity"] == "information"


def test_lean_eval_assemble_respects_own_imports() -> None:
    """A first part carrying its own import header suppresses the
    Mathlib auto-preamble; explicit imports win over both."""
    from Tooling.serve import lean_eval as le
    text, n_pre, _ = le._assemble([("defs", "import Mathlib\ndef a := 1")],
                                  imports=[])
    assert n_pre == 0 and text.startswith("import Mathlib\n")
    text, n_pre, _ = le._assemble([("probe", "#print axioms Foo.bar")],
                                  imports=["Library.X.Y"])
    assert n_pre == 1 and text.startswith("import Library.X.Y\n")


def test_lean_eval_warming_and_validation(workspace: Path,
                                          monkeypatch) -> None:
    """Gateway not ready → {"status": "warming"} and ONE warm-up kick;
    empty payload → 400; oversized → 413. No toolchain spawn."""
    from Tooling.lsp import lifecycle as gw
    from Tooling.serve import lean_eval as le
    monkeypatch.setattr(gw, "gateway_phase", lambda ws: None)
    kicks: list[Path] = []
    monkeypatch.setattr(gw, "start_gateway", lambda ws: kicks.append(ws))
    client = _client(workspace)
    r = client.post("/api/lean/eval",
                    json={"parts": [{"id": "p", "code": "#check 1"}]})
    assert r.status_code == 200 and r.json()["status"] == "warming"
    # WAIT for the kick, and assert it — the docstring claimed "ONE
    # warm-up kick" and nothing checked it, while the warm-up runs in a
    # daemon thread. Unsynchronised, that thread can outlive this test's
    # patch and reach the REAL `start_gateway`, which launches a Lean
    # gateway mid-suite and can kill the operator's warm one. Same shape
    # as the shutdown thread (`_schedule_process_exit`); asserting the
    # effect is also what pins the thread inside the patch's lifetime.
    for _ in range(50):
        if kicks:
            break
        import time as _t
        _t.sleep(0.02)
    assert kicks == [workspace]
    assert client.post("/api/lean/eval",
                       json={"parts": [{"id": "p", "code": "  "}]}
                       ).status_code == 400
    assert client.post(
        "/api/lean/eval",
        json={"parts": [{"id": "p", "code": "x" * (le._MAX_CODE + 1)}]}
    ).status_code == 413


def test_lean_eval_ready_path_stages_and_maps(workspace: Path,
                                              monkeypatch) -> None:
    """Ready gateway → staged file written under .asterism/eval, passed
    to verify_file with write_olean=False, diagnostics mapped per part,
    staged file unlinked."""
    from Tooling.lsp import lifecycle as gw
    monkeypatch.setattr(gw, "gateway_phase", lambda ws: "ready")
    seen: dict = {}

    def fake_verify(path, **kw):
        seen["text"] = Path(path).read_text(encoding="utf-8")
        seen["path"] = Path(path)
        seen["kw"] = kw
        return {"ok": False, "diagnostics": [
            {"line": 2, "col": 1, "severity": "error", "message": "boom"}]}

    monkeypatch.setattr(gw, "verify_file", fake_verify)
    client = _client(workspace)
    r = client.post("/api/lean/eval",
                    json={"parts": [{"id": "probe", "code": "#check 1"}]})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok" and d["ok"] is False
    assert d["parts"]["probe"] == [
        {"line": 1, "col": 1, "severity": "error", "message": "boom"}]
    assert seen["kw"]["write_olean"] is False
    assert seen["text"] == "import Mathlib\n#check 1\n"
    assert ".asterism" in str(seen["path"]) and not seen["path"].exists()


def test_lean_eval_assemble_hoists_later_part_imports() -> None:
    """Root-style later parts: `Problems.*` imports are blanked in place
    (content is inlined above), duplicates dedup against the first
    part's own header, and line counts never shift."""
    from Tooling.serve import lean_eval as le
    defs = "import Mathlib\n\nnamespace P\ndef a := 1\nend P"
    root = ("import Mathlib\nimport Problems.X.Defs\n\n"
            "namespace P\ntheorem main : True := trivial\nend P")
    text, n_pre, spans = le._assemble([("defs", defs), ("root", root)],
                                      imports=[])
    assert n_pre == 0                     # defs opens with its own header
    assert "import Problems.X.Defs" not in text
    assert text.count("import Mathlib") == 1
    lines = text.splitlines()
    assert lines[spans[1][1] - 1] == "" and lines[spans[1][1]] == ""
    assert spans[1][2] - spans[1][1] + 1 == len(root.splitlines())


def test_lean_session_ws_sync_and_cursor(workspace: Path,
                                         monkeypatch) -> None:
    """WS bridge: sync assembles parts, registers an interactive
    session, maps diagnostics per part, carries the cursor goal;
    cursor-only messages query the goal without re-sync; disconnect
    releases the session."""
    from Tooling.lsp import lifecycle as gw
    from Tooling.serve import lean_eval as le
    monkeypatch.setattr(le, "_warm_started", False)
    monkeypatch.setattr(gw, "gateway_phase", lambda ws: "ready")
    calls: list = []

    def fake_register(content):
        calls.append(("register", content))
        return {"session_token": "tok1"}

    def fake_sync(token, content, line=None, col=0):
        calls.append(("sync", token, line, col))
        return {"diagnostics": [
            {"line": 2, "col": 0, "severity": "error", "message": "bad"}],
            "goal": "⊢ True", "note": None}

    def fake_goal(token, line, col):
        calls.append(("goal", token, line, col))
        return {"goal": "⊢ 2 + 2 = 4", "note": None}

    def fake_release(token):
        calls.append(("release", token))
        return {"ok": True}

    monkeypatch.setattr(gw, "interactive_register", fake_register)
    monkeypatch.setattr(gw, "interactive_sync", fake_sync)
    monkeypatch.setattr(gw, "interactive_goal", fake_goal)
    monkeypatch.setattr(gw, "interactive_release", fake_release)

    client = _client(workspace)
    with client.websocket_connect("/api/lean/session") as ws:
        ws.send_json({"type": "sync", "seq": 1,
                      "parts": [{"id": "defs", "code": "def a := 1"}],
                      "cursor": {"part": "defs", "line": 1, "col": 3}})
        r = ws.receive_json()
        assert r["type"] == "state" and r["seq"] == 1
        # global line 2 (after the auto `import Mathlib`) → defs line 1
        assert r["parts"]["defs"] == [
            {"line": 1, "col": 0, "severity": "error", "message": "bad"}]
        assert r["goal"] == "⊢ True"
        ws.send_json({"type": "cursor", "seq": 2,
                      "cursor": {"part": "defs", "line": 1, "col": 0}})
        r2 = ws.receive_json()
        assert r2["type"] == "goal" and r2["goal"] == "⊢ 2 + 2 = 4"
    assert ("release", "tok1") in calls
    # sync carried the cursor mapped to the assembled frame (line 2)
    assert ("sync", "tok1", 2, 3) in calls


def test_lean_session_ws_busy_and_warming(workspace: Path,
                                          monkeypatch) -> None:
    """Reserved slot held elsewhere → busy; cold gateway → warming."""
    from Tooling.lsp import lifecycle as gw
    from Tooling.serve import lean_eval as le
    monkeypatch.setattr(le, "_warm_started", True)  # no warm kick
    monkeypatch.setattr(gw, "gateway_phase", lambda ws: "ready")
    monkeypatch.setattr(gw, "interactive_register",
                        lambda content: {"error": "interactive slot busy",
                                         "http_status": 409})
    client = _client(workspace)
    with client.websocket_connect("/api/lean/session") as ws:
        ws.send_json({"type": "sync", "seq": 7,
                      "parts": [{"id": "p", "code": "#check 1"}]})
        r = ws.receive_json()
        assert r["type"] == "busy" and r["seq"] == 7
    monkeypatch.setattr(gw, "gateway_phase", lambda ws: None)
    with client.websocket_connect("/api/lean/session") as ws:
        ws.send_json({"type": "sync", "seq": 8,
                      "parts": [{"id": "p", "code": "#check 1"}]})
        r = ws.receive_json()
        assert r["type"] == "warming" and r["seq"] == 8


# ---------------------------------------------------------------------
# POST /api/shutdown — quit the whole installation
# ---------------------------------------------------------------------
#
# Three processes, and the third is the one a reader could not guess:
# the Lean gateway is spawned to OUTLIVE the engine (warming Mathlib
# costs minutes) and nothing in the product ever ends it. The laws worth
# pinning are about CONSENT, not about the killing: a live run is not
# something this button gets to decide is expendable.

def test_shutdown_refuses_while_the_engine_is_running(
        tmp_path: Path, monkeypatch) -> None:
    import Tooling.core.cli as _cli
    monkeypatch.setattr(_cli, "daemon_status", lambda ws: {
        "running": True, "pid": 111, "scope": "Cmp.a", "in_flight": 3})
    r = TestClient(create_app(tmp_path)).post("/api/shutdown", json={})
    assert r.status_code == 409
    # the refusal has to say what it is protecting, or it is just a wall
    detail = r.json()["detail"]
    assert "Cmp.a" in detail and "3 agent" in detail


def test_shutdown_preview_names_all_three(tmp_path: Path, monkeypatch) -> None:
    import Tooling.core.cli as _cli
    monkeypatch.setattr(_cli, "daemon_status", lambda ws: {
        "running": True, "pid": 111, "scope": "Cmp.a",
        "in_flight": 2, "gateway": "ready"})
    d = TestClient(create_app(tmp_path)).get("/api/shutdown/preview").json()
    assert d["daemon"] == {"running": True, "scope": "Cmp.a", "in_flight": 2}
    assert d["gateway"]["phase"] == "ready"
    assert d["console"]["pid"] > 0


def test_shutdown_with_force_stops_the_engine_first(
        tmp_path: Path, monkeypatch) -> None:
    """Order is the contract: the engine, then the gateway that outlives
    it, then this process — a console that killed itself first could not
    report what happened to the other two."""
    import Tooling.core.cli as _cli
    import Tooling.serve.app as _app
    calls: "list[str]" = []
    monkeypatch.setattr(_cli, "daemon_status", lambda ws: {
        "running": True, "pid": 111, "scope": "Cmp.a", "in_flight_leases": 1})
    monkeypatch.setattr(_cli, "daemon_stop",
                        lambda ws, force=False: (calls.append(
                            f"daemon(force={force})"), (0, "stopped"))[1])
    # Replace the whole SCHEDULING mechanism, not just `os._exit`.
    # Patching the exit call alone leaves a thread sleeping past
    # teardown, and it wakes into the real one and kills the pytest
    # worker — see `_schedule_process_exit` for the full autopsy. The
    # contract under test is the ORDER, which never needed a process to
    # actually die.
    monkeypatch.setattr(_app, "_schedule_process_exit",
                        lambda: calls.append("exit"))
    from Tooling.lsp import lifecycle as _gw
    monkeypatch.setattr(_gw, "_ping_health", lambda timeout=1.0: {"pid": 222})
    monkeypatch.setattr(_gw, "_kill_stale_gateway",
                        lambda pid: calls.append(f"gateway({pid})"))
    r = TestClient(create_app(tmp_path)).post("/api/shutdown",
                                              json={"force": True})
    assert r.status_code == 200
    assert r.json()["stopped"] == ["engine", "Lean gateway", "console"]
    assert calls[:2] == ["daemon(force=True)", "gateway(222)"]


# ---------------------------------------------------------------------
# provider rows: the api-key flavor (zen, 2026-08-22)
# ---------------------------------------------------------------------

def _zen_row(workspace: Path) -> dict:
    body = _client(workspace).get("/api/meta").json()
    rows = [p for p in body["providers"] if p["name"] == "zen"]
    assert rows, "zen is declared — it must have a row"
    return rows[0]


def test_api_key_provider_reports_presence_never_value(
        workspace: Path, monkeypatch) -> None:
    """The console has no input field for a key (owner, 2026-08-22):
    the row says WHICH variable and WHETHER it is set, and nothing else
    — the value must not cross the HTTP layer."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    row = _zen_row(workspace)
    assert row["env_key"] == "OPENROUTER_API_KEY"
    assert row["key_present"] is False

    secret = "sk-or-v1-0123456789abcdef"
    (workspace / ".env").write_text(
        f"# comment\nOPENROUTER_API_KEY={secret}\n", encoding="utf-8")
    body = _client(workspace).get("/api/meta").json()
    row = [p for p in body["providers"] if p["name"] == "zen"][0]
    assert row["key_present"] is True
    assert secret not in json.dumps(body)  # presence, never the value


def test_env_key_empty_assignment_is_absent(
        workspace: Path, monkeypatch) -> None:
    # `NAME=` with nothing after it is how a key gets REMOVED in a
    # .env; reporting it present would point the reader away from
    # the actual fix
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (workspace / ".env").write_text(
        "OPENROUTER_API_KEY=\n", encoding="utf-8")
    assert _zen_row(workspace)["key_present"] is False


def test_env_beats_dotenv_for_presence(workspace: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    assert _zen_row(workspace)["key_present"] is True


def test_zen_installed_means_the_carrier_binary(
        workspace: Path, monkeypatch) -> None:
    """zen declares exe_name='codex' — installed answers about the
    binary it actually runs, never about a `zen` that will not exist."""
    import shutil as _sh
    seen: list[str] = []

    def fake_which(name: str) -> "str | None":
        seen.append(name)
        return r"C:\fake\codex.exe" if name == "codex" else None

    monkeypatch.setattr(_sh, "which", fake_which)
    row = _zen_row(workspace)
    assert row["installed"] is True
    assert "zen" not in seen


# ---------------------------------------------------------------------
# the update flow: VERSION stamp + the console-only recycle (2026-08-22)
# ---------------------------------------------------------------------

def test_meta_reports_loaded_and_disk_version(tmp_path: Path) -> None:
    """`version` is what THIS process started from (read once);
    `disk_version` is what an unzip left there now. Differing is how
    both the launcher and the banner detect a half-landed update."""
    (tmp_path / "VERSION").write_text("aaaa11112222\n", encoding="utf-8")
    c = TestClient(create_app(tmp_path))
    d = c.get("/api/meta").json()
    assert d["version"] == "aaaa11112222"
    assert d["disk_version"] == "aaaa11112222"
    # the unzip lands a new stamp under the LIVE console
    (tmp_path / "VERSION").write_text("bbbb33334444\n", encoding="utf-8")
    d = c.get("/api/meta").json()
    assert d["version"] == "aaaa11112222"   # unchanged: the loaded code
    assert d["disk_version"] == "bbbb33334444"


def test_meta_version_null_in_a_dev_workspace(tmp_path: Path) -> None:
    d = TestClient(create_app(tmp_path)).get("/api/meta").json()
    assert d["version"] is None
    assert d["disk_version"] is None


def test_shutdown_console_only_touches_nothing_else(
        tmp_path: Path, monkeypatch) -> None:
    """The update recycle: the engine reloads code by its own skew
    handoff and the gateway holds a warm Mathlib — a console restart
    must not cost either. Even a RUNNING engine is no reason to
    refuse: replacing the console abandons no work."""
    import Tooling.core.cli as _cli
    import Tooling.serve.app as _app
    calls: "list[str]" = []
    monkeypatch.setattr(_cli, "daemon_status", lambda ws: (
        calls.append("daemon_status"),
        {"running": True, "pid": 111, "scope": "Cmp.a",
         "in_flight_leases": 3})[1])
    monkeypatch.setattr(_cli, "daemon_stop",
                        lambda ws, force=False: (calls.append("daemon_stop"),
                                                 (0, "stopped"))[1])
    monkeypatch.setattr(_app, "_schedule_process_exit",
                        lambda: calls.append("exit"))
    from Tooling.lsp import lifecycle as _gw
    monkeypatch.setattr(_gw, "_kill_stale_gateway",
                        lambda pid: calls.append("gateway"))
    r = TestClient(create_app(tmp_path)).post(
        "/api/shutdown", json={"console_only": True})
    assert r.status_code == 200
    assert r.json()["stopped"] == ["console"]
    assert calls == ["exit"]


# ---------------------------------------------------------------------
# the second kind of meter: a backend with no endpoint, read back off
# the ledger it writes itself (codex, 2026-08-26)
# ---------------------------------------------------------------------

def _rollout(workspace: Path, name: str, *, primary: dict | None,
             secondary: dict | None = None, plan: str = "pro",
             reached: object = None) -> Path:
    """A codex rollout as the CLI leaves it: the quota reading rides a
    `token_count` event, and there is other traffic around it."""
    d = workspace / ".asterism" / "codex_sessions" / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"rollout-{name}.jsonl"
    lines = [json.dumps({"payload": {"type": "item.completed", "text": "x"}})]
    if primary is not None:
        lines.append(json.dumps({"payload": {
            "type": "token_count",
            "rate_limits": {"limit_id": "codex", "plan_type": plan,
                            "primary": primary, "secondary": secondary,
                            "rate_limit_reached_type": reached}}}))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_session_log_quota_names_windows_by_their_own_length(
        workspace: Path) -> None:
    """codex reports one weekly window on some accounts and 5-hour +
    weekly on others (both measured in one workspace, 2026-08-26), so
    a window is named by `window_minutes`, never by its position."""
    from Tooling.serve.run import log_quota, reset_quota_memo
    reset_quota_memo()
    _rollout(workspace, "s1",
             primary={"used_percent": 12.0, "window_minutes": 300,
                      "resets_at": 1788272023},
             secondary={"used_percent": 8.0, "window_minutes": 10080,
                        "resets_at": 1788472023})
    rows = log_quota(workspace)
    assert [r["provider"] for r in rows] == ["codex"]
    assert [(w["minutes"], w["utilization"]) for w in rows[0]["windows"]] == [
        (300, 12.0), (10080, 8.0)]
    assert rows[0]["plan"] == "pro"
    # the age travels with the reading — a meter nobody asked for must
    # never be published as a live one
    assert rows[0]["measured_at"] is not None
    assert rows[0]["windows"][0]["resets_at"].startswith("2026-")


def test_session_log_quota_takes_the_newest_reading(workspace: Path) -> None:
    """Newest rollout wins, and one that carries no reading (a spawn
    that died before its first turn) does not blank the meter."""
    import os
    import time
    from Tooling.serve.run import log_quota, reset_quota_memo
    old = _rollout(workspace, "old",
                   primary={"used_percent": 3.0, "window_minutes": 10080,
                            "resets_at": 1788272023})
    new = _rollout(workspace, "new",
                   primary={"used_percent": 41.0, "window_minutes": 10080,
                            "resets_at": 1788272023})
    empty = _rollout(workspace, "empty", primary=None)
    now = time.time()
    os.utime(old, (now - 300, now - 300))
    os.utime(new, (now - 60, now - 60))
    os.utime(empty, (now, now))       # newest, and it says nothing
    reset_quota_memo()
    rows = log_quota(workspace)
    assert rows[0]["windows"][0]["utilization"] == 41.0
    reset_quota_memo()


def test_run_payload_carries_the_logged_meter(workspace: Path) -> None:
    _open_db(workspace).close()
    from Tooling.serve.run import reset_quota_memo
    _rollout(workspace, "s1",
             primary={"used_percent": 8.0, "window_minutes": 10080,
                      "resets_at": 1788272023})
    reset_quota_memo()
    d = _client(workspace).get("/api/run").json()
    assert d["quota_logged"][0]["provider"] == "codex"
    reset_quota_memo()


# ---------------------------------------------------------------------
# the account switch, for whoever declares one
# ---------------------------------------------------------------------

def test_provider_rows_offer_the_switch_by_declaration(
        workspace: Path) -> None:
    """claude and codex both declare a console sign-in; the API-key and
    borrowed-session backends declare none, and must not grow a button
    that would sign into an account they do not use."""
    rows = {p["name"]: p for p in
            _client(workspace).get("/api/meta").json()["providers"]}
    assert rows["claude"]["can_login"] and rows["claude"]["can_logout"]
    assert rows["codex"]["can_login"] and rows["codex"]["can_logout"]
    # zen rides codex's binary and inherits its declaration wholesale —
    # the fields it must NOT inherit are its credential ones
    assert not rows["zen"]["can_login"]
    assert not rows["zen"]["can_logout"]
    assert not rows["antigravity"]["can_login"]


def test_provider_logout_retires_the_declared_file(
        workspace: Path, monkeypatch, tmp_path: Path) -> None:
    """Sign-out renames under a timestamp — never deletes: a switch the
    owner cannot undo by hand is the wrong default for a quota move."""
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    creds = home / ".codex" / "auth.json"
    creds.write_text('{"tokens": {}}', encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    c = _client(workspace)
    assert c.post("/api/providers/codex/logout").json()["logged_out"] is True
    assert not creds.exists()
    assert [p.name for p in (home / ".codex").iterdir()][0].startswith(
        "auth.json.bak-")
    # idempotent: a second press says so instead of erroring
    assert c.post("/api/providers/codex/logout").json()["logged_out"] is False


def test_provider_login_is_declared_not_named(
        workspace: Path, monkeypatch) -> None:
    """The argv comes from the declaration, and a backend that declares
    none is refused rather than guessed at."""
    import Tooling.serve.app as _app
    spawned: "list[tuple[str, tuple]]" = []
    monkeypatch.setattr(_app, "spawn_cli_login",
                        lambda exe, argv: spawned.append((exe, argv)))
    import shutil as _sh
    monkeypatch.setattr(_sh, "which", lambda n: r"C:\fake\codex.exe")
    c = _client(workspace)
    assert c.post("/api/providers/codex/login").json()["opened"] is True
    assert spawned and spawned[0][1] == ("login",)
    assert c.post("/api/providers/zen/login").status_code == 409
    assert c.post("/api/providers/nope/login").status_code == 404


def test_serve_cli_accepts_a_host_override(monkeypatch):
    """Fleet era (2026-09-01): the cockpit's localhost-only binding made
    a remote node's UI unreachable over the tailnet. `--host` is an
    explicit opt-in; the default stays loopback."""
    import importlib
    m = importlib.import_module("Tooling.core.cli.main")
    seen = {}
    monkeypatch.setattr(m, "cmd_serve", lambda a: seen.update(vars(a)) or 0)
    m.main(["serve", "--host", "100.114.139.65"])
    assert seen["host"] == "100.114.139.65"
    seen.clear()
    m.main(["serve"])
    assert seen["host"] == "127.0.0.1"


# ---------------------------------------------------------------------
# Projects (human_interface_design.md §3.1)
# ---------------------------------------------------------------------


def test_projects_endpoint_lists_what_the_backfill_filed(
        workspace: Path) -> None:
    """A Project is a row, so the board reads it from the DB rather than
    re-deriving prefixes: registering `Erdos.p1` files it under `Erdos`,
    and the listing carries the description a card shows."""
    conn = _open_db(workspace)
    _add_problem(conn, "Erdos.p1")
    conn.execute("INSERT INTO projects (name, description, created_at)"
                 " VALUES ('Erdos', 'the shelf', ?)", (db.now(),))
    conn.execute("UPDATE problems SET project = 'Erdos'")
    conn.commit()
    conn.close()
    r = _client(workspace).get("/api/projects")
    assert r.status_code == 200, r.text
    assert r.json()["projects"] == [
        {"name": "Erdos", "description": "the shelf", "problems": 1}]


def test_create_project_conflicts_instead_of_clobbering(
        workspace: Path) -> None:
    """POST goes through the state function, so its refusals arrive as
    409 (the resolve_amend pattern) rather than as a silent upsert."""
    _open_db(workspace).close()
    c = _client(workspace)
    assert c.post("/api/projects",
                  json={"name": "Erdos", "description": "the shelf"}
                  ).status_code == 200
    assert c.post("/api/projects", json={"name": "Erdos"}).status_code == 409
    # 2026-09-02 ruling (HID §3.2 appendix): a malformed NAME is 422 —
    # the same answer `/api/problems/create` gives — because 409 told the
    # person the name was taken when it was simply not a name.
    assert c.post("/api/projects", json={"name": "a b"}).status_code == 422
    assert [p["name"] for p in c.get("/api/projects").json()["projects"]] \
        == ["Erdos"]


def test_patch_project_renames_and_the_problems_follow(
        workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "Erdos.p1")
    conn.execute("INSERT INTO projects (name, description, created_at)"
                 " VALUES ('Erdos', '', ?)", (db.now(),))
    conn.execute("UPDATE problems SET project = 'Erdos'")
    conn.commit()
    conn.close()
    c = _client(workspace)
    r = c.patch("/api/projects/Erdos",
                json={"name": "ErdosProblems", "description": "the shelf"})
    assert r.status_code == 200, r.text
    assert c.get("/api/projects").json()["projects"] == [
        {"name": "ErdosProblems", "description": "the shelf", "problems": 1}]
    assert c.patch("/api/projects/ghost",
                   json={"description": "x"}).status_code == 404


def test_delete_project_refuses_while_a_problem_names_it(
        workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "Erdos.p1")
    conn.execute("INSERT INTO projects (name, description, created_at)"
                 " VALUES ('Erdos', '', ?)", (db.now(),))
    conn.execute("UPDATE problems SET project = 'Erdos'")
    conn.commit()
    conn.close()
    c = _client(workspace)
    assert c.delete("/api/projects/Erdos").status_code == 409
    assert c.delete("/api/projects/ghost").status_code == 404
    conn = db.connect(workspace / "asterism.db")
    conn.execute("UPDATE problems SET project = NULL")
    conn.commit()
    conn.close()
    assert c.delete("/api/projects/Erdos").status_code == 200
    assert c.get("/api/projects").json()["projects"] == []


# ---------------------------------------------------------------------
# Human commands (human_interface_design.md §3.3)
# ---------------------------------------------------------------------


def _goal_row(conn: sqlite3.Connection, problem: str, slug: str = "main",
              origin: str = "root") -> int:
    return db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement="T", origin=origin, depth=0)


def test_post_command_returns_a_queued_receipt(workspace: Path) -> None:
    """§3.3: serve INSERTs the queue row and nothing else — the receipt
    is the id, the outcome is looked up later. 202, because the work has
    not happened yet."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = _goal_row(conn, "p")
    conn.commit()
    conn.close()
    c = _client(workspace)
    r = c.post("/api/commands", json={
        "problem": "p", "kind": "ConfirmShelve",
        "payload": {"target_goal_id": gid, "reason": "stop"},
        "idempotency_key": "k1"})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "queued"
    cid = r.json()["id"]
    got = c.get(f"/api/commands/{cid}")
    assert got.status_code == 200
    assert got.json()["kind"] == "ConfirmShelve"
    assert got.json()["status"] == "queued"
    # the retry is the same command, not a second one
    again = c.post("/api/commands", json={
        "problem": "p", "kind": "ConfirmShelve",
        "payload": {"target_goal_id": gid, "reason": "stop"},
        "idempotency_key": "k1"})
    assert again.json()["id"] == cid


def test_command_refusals_are_404_and_422(workspace: Path) -> None:
    """The `resolve_amend` shape the Project endpoints already use:
    KeyError = the named thing is not there (404), a malformed request
    is 422 — and a ghost receipt is a 404, not an empty 200."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    conn.close()
    c = _client(workspace)
    assert c.post("/api/commands", json={
        "problem": "ghost", "kind": "ConfirmShelve", "payload": {},
        "idempotency_key": "k"}).status_code == 404
    assert c.post("/api/commands", json={
        "problem": "p", "kind": "Ingest", "payload": {},
        "idempotency_key": "k2"}).status_code == 422
    assert c.get("/api/commands/999").status_code == 404


def test_command_preview_names_the_cascade(workspace: Path) -> None:
    """The confirm window's data (§1.3): read-only, no queue row."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    root = _goal_row(conn, "p")
    sid = db.insert_strategy(conn, goal_id=root,
                             lean_path="Problems/p/proofs/S_x.lean",
                             created_by="test")
    kid = _goal_row(conn, "p", "kid", origin="backward")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=kid, position=0)
    conn.commit()
    conn.close()
    c = _client(workspace)
    r = c.post("/api/commands/preview", json={
        "problem": "p", "kind": "ConfirmShelve",
        "payload": {"target_goal_id": root}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cascade"] is True
    assert [a["id"] for a in body["affected"]] == [root, kid]
    conn2 = _open_db(workspace)
    assert conn2.execute(
        "SELECT COUNT(*) FROM human_commands").fetchone()[0] == 0


def test_start_many_requires_every_problem_to_exist(
        workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """§1.4: the multi-problem run takes an explicit list and refuses
    patterns — the same post-incident defence `/api/daemon/start` has.
    A missing name is a 404 that says WHICH."""
    conn = _open_db(workspace)
    _add_problem(conn, "a")
    _add_problem(conn, "b")
    conn.close()
    seen = {}
    from Tooling.core import cli as _cli
    monkeypatch.setattr(
        _cli, "daemon_start",
        lambda ws, *, scope=None, once=False, **kw: (
            seen.update(scope=scope, once=once) or (0, "started")))
    c = _client(workspace)
    missing = c.post("/api/daemon/start-many",
                     json={"problems": ["a", "ghost"]})
    assert missing.status_code == 404
    assert "ghost" in missing.json()["detail"]
    assert c.post("/api/daemon/start-many",
                  json={"problems": ["a", "b%"]}).status_code == 404
    ok = c.post("/api/daemon/start-many", json={"problems": ["a", "b"]})
    assert ok.status_code == 200, ok.text
    assert db.scope_names(seen["scope"]) == ["a", "b"]


def test_detail_decisions_carry_the_actor(workspace: Path) -> None:
    """HID §3.2: `actor` is semantic, so the reading layer carries it —
    a reader who cannot see that a PERSON decided cannot tell a human
    park (terminal) from the machine's own (a wait)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    did = _add_decision(conn, "p", kind="ConfirmShelve", reason="stop")
    conn.execute("UPDATE strategist_decisions SET actor = 'human'"
                 " WHERE id = ?", (did,))
    conn.commit()
    conn.close()
    detail = _client(workspace).get("/api/problems/p").json()
    assert detail["decisions"][0]["actor"] == "human"


def test_detail_carries_the_ingest_report(workspace: Path) -> None:
    """HID §3.4: the terminal's human-readable summary is on the problem
    read — the page a mathematician opens, not a file they must find.
    Null before the terminal, and null for every problem whose Strategist
    wrote none."""
    conn = _open_db(workspace)
    _add_problem(conn, "p", ingest_report="# What was proved\n\nThe bound.")
    _add_problem(conn, "q")
    conn.close()
    c = _client(workspace)
    assert c.get("/api/problems/p").json()["ingest_report"] \
        == "# What was proved\n\nThe bound."
    assert c.get("/api/problems/q").json()["ingest_report"] is None


def test_a_command_missing_its_own_field_is_422_at_the_post(
        workspace: Path) -> None:
    """§3.3 ruling 2026-09-02: §1.3's per-kind requirements are checked
    when the person presses the button, not minutes later on the daemon's
    tick — and nothing is queued, so there is no receipt to chase."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = _goal_row(conn, "p")
    conn.commit()
    conn.close()
    c = _client(workspace)
    r = c.post("/api/commands", json={
        "problem": "p", "kind": "ConfirmShelve",
        "payload": {"target_goal_id": gid}, "idempotency_key": "no-reason"})
    assert r.status_code == 422, r.text
    assert "reason" in r.json()["detail"]
    conn2 = _open_db(workspace)
    assert conn2.execute(
        "SELECT COUNT(*) FROM human_commands").fetchone()[0] == 0


# ---------------------------------------------------------------------
# Project documents (human_interface_design.md §3.6)
# ---------------------------------------------------------------------


def _with_project(workspace: Path, name: str = "Erdos") -> None:
    conn = _open_db(workspace)
    conn.execute("INSERT INTO projects (name, description, created_at)"
                 " VALUES (?, '', ?)", (name, db.now()))
    conn.commit()
    conn.close()


def test_docs_round_trip_through_the_endpoints(workspace: Path) -> None:
    """The file surface a person edits: list, write, read back, remove.
    The tree is what the left rail renders, so a folder is an entry in
    its own right (§1.2-3)."""
    _with_project(workspace)
    c = _client(workspace)
    assert c.get("/api/projects/Erdos/docs").json()["entries"] == []
    assert c.put("/api/projects/Erdos/docs/user/notes.md",
                 json={"content": "# hello\n"}).status_code == 200
    entries = c.get("/api/projects/Erdos/docs").json()["entries"]
    assert [(e["path"], e["kind"]) for e in entries] == [
        ("user", "dir"), ("user/notes.md", "file")]
    r = c.get("/api/projects/Erdos/docs/user/notes.md")
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "# hello\n"
    assert c.delete("/api/projects/Erdos/docs/user/notes.md"
                    ).status_code == 200
    assert c.get("/api/projects/Erdos/docs/user/notes.md"
                 ).status_code == 404


def test_docs_put_writes_only_the_user_area(workspace: Path) -> None:
    """§3.6: this door writes `user/`. `agent/` is the Assistant's
    shelf and reaching it from here would make the two areas one."""
    _with_project(workspace)
    c = _client(workspace)
    r = c.put("/api/projects/Erdos/docs/agent/summary.md",
              json={"content": "x"})
    assert r.status_code == 422, r.text
    assert "user/" in r.json()["detail"]
    assert not (workspace / "Problems" / "Erdos" / "_docs" / "agent"
                ).exists()


def test_docs_put_creates_a_folder(workspace: Path) -> None:
    _with_project(workspace)
    c = _client(workspace)
    assert c.put("/api/projects/Erdos/docs/user/chapter",
                 json={"kind": "dir"}).status_code == 200
    assert c.get("/api/projects/Erdos/docs").json()["entries"] == [
        {"path": "user", "kind": "dir"},
        {"path": "user/chapter", "kind": "dir"}]


def test_docs_refuse_a_path_that_leaves_the_root(workspace: Path) -> None:
    """Percent-encoded, because a plain `..` never survives the trip: an
    HTTP client normalises it away before the request is sent, so the
    form that actually ARRIVES at the endpoint is the escaped one."""
    _with_project(workspace)
    r = _client(workspace).put(
        "/api/projects/Erdos/docs/user/%2e%2e/%2e%2e/%2e%2e/escape.md",
        json={"content": "x"})
    assert r.status_code == 422, r.text
    assert not (workspace / "Problems" / "escape.md").exists()


def test_docs_of_an_unknown_project_are_404(workspace: Path) -> None:
    _with_project(workspace)
    assert _client(workspace).get(
        "/api/projects/ghost/docs").status_code == 404
