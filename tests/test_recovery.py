

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
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('P', 'M.md', 't')")
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
