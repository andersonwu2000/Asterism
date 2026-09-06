

def test_startup_sweeps_fossil_rows_for_deleted_problems(tmp_path):
    """A queue row whose problem no longer exists is undispatchable
    under EVERY scope forever, yet still pollutes unscoped queue
    readings (2026-08-26 census: Test.* smoke rows queued since July).
    Scope-blind sweep, unleased only; rows for LIVE problems — even
    out-of-scope paused ones — survive."""
    from Tooling.state import db as _db, recovery
    conn = _db.connect(tmp_path / "f.db")
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at) VALUES ('P','t')")
    _db.enqueue(conn, kind="Strategist", target_id="1", problem="P",
                target_kind="Group")
    _db.enqueue(conn, kind="Strategist", target_id="Test.gone",
                problem="Test.gone", target_kind="Problem")
    _db.enqueue(conn, kind="Strategist", target_id="Test.leased",
                problem="Test.leased", target_kind="Problem")
    # Leased by a LIVE owner (this process). A dead fake pid used to
    # stand in here, which held only while dead-owner leases outside
    # the scope were left alone; since 2026-08-30 a dead owner is swept
    # in every scope (owner ruling 2026-08-27) — only a live one is
    # respected, fossil or not.
    import os
    conn.execute("UPDATE queue SET owner_pid = ? "
                 "WHERE problem = 'Test.leased'", (os.getpid(),))
    conn.commit()

    # scoped to another problem: the fossil sweep must still run
    recovery.recover_at_startup(conn, workspace=None, scope="Q.%")

    left = {r["problem"] for r in conn.execute(
        "SELECT problem FROM queue")}
    assert "Test.gone" not in left, "fossil for a deleted problem stayed"
    assert "P" in left, "a live problem's row must survive a foreign scope"
    assert "Test.leased" in left, "never yank a leased row, fossil or not"


def test_startup_closes_sub_projects_orphaned_before_the_cascade(tmp_path):
    """`groups.set_status` cascades downward from 2026-08-16, so no NEW
    orphan can appear — but every tree built before it carries them, and
    they are not idle. union_closed had six such groups across two
    lines; one spent twenty-two bricks and three hours binary-splitting
    a mask space for a charter its grandparent had withdrawn. Startup is
    the one moment nothing is in flight, so it is where the existing
    tree is brought under the law."""
    from Tooling.state import db as _db, groups as _groups, recovery
    conn = _db.connect(tmp_path / "a.db")
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES ('P', 't')")
    top = _groups.ensure_top_group(conn, "P")
    mid = _groups.open_group(conn, problem="P", parent_group_id=top,
                             charter="mid")
    kid = _groups.open_group(conn, problem="P", parent_group_id=mid,
                             charter="kid")
    grand = _groups.open_group(conn, problem="P", parent_group_id=kid,
                               charter="grand")
    # The pre-cascade shape: an ancestor retired, descendants left live.
    conn.execute("UPDATE groups SET status = 'closed' WHERE id = ?", (mid,))
    conn.commit()

    recovery.recover_at_startup(conn, workspace=None)

    for g in (kid, grand):
        assert _groups.get(conn, g)["status"] == "closed", (
            f"group {g} was left working a withdrawn charter")
    assert _groups.get(conn, top)["status"] == "active", (
        "the sweep must not reach a group with no retired ancestor")


def test_the_orphan_sweep_spares_an_unanswered_theory_request(tmp_path,
                                                              monkeypatch):
    """`.attempts/<pid>/` is ephemeral by design and the startup sweep
    empties it — but the theory layer now keeps its resume point there.
    A dir carrying `_theorize.json` for a decision whose outcome is
    still NULL is the ONLY copy of a document that cost hours of quota
    (union_closed g694, 2026-09-06), so the sweep steps over it; once
    the request is settled there is nothing to resume and it goes.
    """
    monkeypatch.chdir(tmp_path)
    from Tooling.state import db as _db, groups as _groups, recovery
    from Tooling.pipeline.theorist import checkpoint as _ck
    conn = _db.connect(tmp_path / "t.db")
    _db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at) VALUES ('P','t')")
    gid = _groups.ensure_top_group(conn, "P")
    ids = {}
    for tag, outcome in (("open", None), ("settled", "success")):
        cur = conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, group_id, outcome, created_at,"
            " updated_at) VALUES ('P', 0, 'routine', 'Theorize', ?, ?,"
            " 't', 't')", (gid, outcome))
        ids[tag] = int(cur.lastrowid)
    conn.commit()

    for tag, did in ids.items():
        d = tmp_path / ".attempts" / f"pid-{tag}"
        d.mkdir(parents=True)
        (d / "report.md").write_text("the document\n", encoding="utf-8")
        _ck.write(d, decision_id=did, group_id=gid, problem="P",
                  author_sid="s", provider="claude", model="m",
                  phase=_ck.PHASE_AWAITING_REVIEW, round_no=1,
                  started_at="t0")
    (tmp_path / ".attempts" / "pid-plain").mkdir()

    recovery.recover_at_startup(conn, workspace=tmp_path)

    assert (tmp_path / ".attempts" / "pid-open" / "report.md").is_file(), (
        "the sweep deleted the only copy of an unanswered request's work")
    assert not (tmp_path / ".attempts" / "pid-settled").exists()
    assert not (tmp_path / ".attempts" / "pid-plain").exists()
