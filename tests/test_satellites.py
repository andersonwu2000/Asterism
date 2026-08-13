"""The satellite registry: what a problem owns, in one place, with
complement-based auditors.

The reset-leak family this closes off (eight incidents, 2026-06 →
2026-08) always had the same anatomy: satellites enumerated by hand at
each operation, and an auditor that read the sweeper's own list — so it
could only ever confirm what the sweeper already knew (d45a17b9: the
verifier and sweeper shared one duplicated tuple and therefore one
blind spot). Here:

  * the DB classification is DERIVED from the schema; a new table that
    is neither derivably problem-keyed nor declared polymorphic fails a
    test by name, so it cannot arrive unclassified;
  * the file registry feeds the sweeper, the verifier AND the
    complement walk, and the complement asks the question the verifier
    cannot: "what exists that nothing claims";
  * auditors REPORT, never delete — widening what reset destroys is
    the operator's decision, made on this evidence.
"""
from __future__ import annotations

import argparse
import fnmatch
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, satellites
from Tooling.core import cli


# ---------------------------------------------------------------- DB side

@pytest.fixture()
def mem() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_schema(conn)
    return conn


def test_every_table_is_classified(mem) -> None:
    """The teeth. A table the auditors cannot ask about is a table
    whose rows outlive their problem invisibly — the reset-leak family
    in schema form."""
    kinds = satellites.classify_tables(mem)
    unclassified = sorted(t for t, k in kinds.items() if k == "UNCLASSIFIED")
    assert not unclassified, (
        "these tables are neither derivably problem-keyed (a `problem` "
        "column, an FK path to problems) nor declared in "
        "satellites.POLYMORPHIC_TABLES — the auditors cannot see their "
        "rows, which is how reset leaks start:\n  "
        + "\n  ".join(unclassified))


def test_a_new_unclassifiable_table_is_caught_by_name(mem) -> None:
    """Mutation check, planted live: the exact violation the guard
    exists for — a new table with no derivable problem linkage."""
    mem.execute("CREATE TABLE mutation_probe (id INTEGER PRIMARY KEY)")
    kinds = satellites.classify_tables(mem)
    assert kinds["mutation_probe"] == "UNCLASSIFIED"


def test_polymorphic_and_survivor_declarations_do_not_rot(mem) -> None:
    """A declaration for a table that no longer exists is a pardon
    nobody is using — same rule as the single-home grandfather list."""
    tables = set(satellites.classify_tables(mem))
    for t in satellites.POLYMORPHIC_TABLES:
        assert t in tables, f"POLYMORPHIC_TABLES entry {t!r} names no table"
    for t, why in satellites.SURVIVES_RESET.items():
        assert t in tables, f"SURVIVES_RESET entry {t!r} names no table"
        assert len(why.strip()) > 40, (
            f"{t}: a survival ruling without a real reason is just a "
            f"blind spot with paperwork")


def _seed_full_problem(mem, problem: str = "wilson") -> None:
    """One row in every problem-keyed surface the wipe must clear."""
    now = db.now()
    mem.execute("PRAGMA foreign_keys = ON")
    mem.execute("INSERT INTO problems (name, manifest_path, created_at)"
                " VALUES (?, 'Manifest.md', ?)", (problem, now))
    mem.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement, origin,"
        " status, created_at, updated_at)"
        " VALUES (?, 'main', 'p/root.lean', 'True', 'root', 'open', ?, ?)",
        (problem, now, now))
    gid = mem.execute("SELECT id FROM goals WHERE problem = ?",
                      (problem,)).fetchone()["id"]
    mem.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at) VALUES (?, '', 'proposed', 'pid-t', ?)", (gid, now))
    sid = mem.execute("SELECT id FROM strategies").fetchone()["id"]
    mem.execute("INSERT INTO strategy_subgoals (strategy_id, subgoal_id,"
                " position) VALUES (?, ?, 0)", (sid, gid))
    mem.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'Inject', ?, ?, ?)",
        (problem, gid, now, now))
    mem.execute(
        "INSERT INTO queue (kind, target_id, target_kind, priority,"
        " problem, created_at) VALUES ('Backward', ?, 'Goal', 10, ?, ?)",
        (str(gid), problem, now))
    mem.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at) VALUES ('pid-1', 'Forward', ?, 'Problem',"
        " 'failed', 'failed', ?)", (problem, now))
    mem.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, ts) VALUES (?, 'Problem', 'pid-1',"
        " 'agent_declined', ?)", (problem, now))
    mem.execute(
        "INSERT INTO kb_entries (type, title, body, problem, created_at)"
        " VALUES ('lesson', 't', 'b', ?, ?)", (problem, now))
    mem.execute(
        "INSERT INTO problem_settings (problem, key, value, updated_at)"
        " VALUES (?, 'k', 'v', ?)", (problem, now))
    mem.execute(
        "INSERT INTO user_file_history (problem, file, sha, body, seen_at)"
        " VALUES (?, 'Root.lean', 'h', '-', ?)", (problem, now))
    mem.execute(
        "INSERT INTO programme_revisions (problem, rev, body, status,"
        " created_at) VALUES (?, 1, 'route', 'passed', ?)", (problem, now))
    mem.execute(
        "INSERT INTO goal_events (goal_id, problem, from_status,"
        " to_status, event, at)"
        " VALUES (?, ?, 'open', 'attempting', 'claim', ?)",
        (gid, problem, now))
    mem.execute(
        "INSERT INTO groups (problem, charter, status, created_at,"
        " updated_at) VALUES (?, 'the root charter', 'active', ?, ?)",
        (problem, now, now))
    mem.execute(
        "INSERT INTO librarian_fail_counts (target_id, n, updated_at)"
        " VALUES (? || char(31) || 'file.lean', 2, ?)", (problem, now))
    mem.execute(
        "INSERT INTO spawn_usage (pipeline_id, kind, problem,"
        " input_tokens, output_tokens, ts)"
        " VALUES ('pid-1', 'Forward', ?, 1, 1, ?)", (problem, now))
    mem.commit()


def test_db_leftovers_sees_what_the_wipe_leaves(mem) -> None:
    """The complement auditor against the REAL wipe. Two facts pinned:

    1. Everything `wipe_problem_rows` promises to clear really goes —
       the only rows the auditor reports afterwards are the two
       DECLARED survivors' (skipped) and the librarian prefix rows,
       whose survival is itself a declared ruling.
    2. The auditor is not decorative: before the wipe it sees rows in
       every askable table."""
    _seed_full_problem(mem)
    before = satellites.db_leftovers(mem, "wilson")
    assert before.get("problems") == 1
    assert before.get("goals") == 1
    assert before.get("queue") == 1
    assert before.get("pipelines") == 1
    # Declared survivors are skipped even while their rows exist.
    assert "spawn_usage" not in before
    assert "librarian_fail_counts" not in before

    cli.wipe_problem_rows(mem, "wilson")
    mem.commit()
    after = satellites.db_leftovers(mem, "wilson")
    assert after == {}, (
        f"wipe_problem_rows left rows the auditor can see: {after} — "
        f"either the wipe grew a blind spot or a new table joined "
        f"without reset coverage. Do NOT silently widen the wipe; "
        f"report it.")
    # The declared survivors DID survive — the ruling is real, not
    # a stale entry covering for an already-clean table.
    assert mem.execute("SELECT COUNT(*) FROM spawn_usage").fetchone()[0] == 1
    assert mem.execute(
        "SELECT COUNT(*) FROM librarian_fail_counts").fetchone()[0] == 1


def test_orphan_rows_sees_the_group_target_class(mem) -> None:
    """The 2026-08-13 finding, as a fixture: Group-targeted pipelines
    rows survive a reset because the wipe clears Goal/Strategy/Problem
    targets only. The global orphan audit is the grain that sees them
    (68 real ones measured on the live DB)."""
    now = db.now()
    mem.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at) VALUES ('pid-g', 'Strategist', '367',"
        " 'Group', 'failed', 'failed', ?)", (now,))
    mem.commit()
    orphans = satellites.orphan_rows(mem)
    assert orphans.get("pipelines(Group target gone)") == 1


# -------------------------------------------------------------- file side

def test_swept_entries_never_claim_user_owned_files() -> None:
    """The one edit that must be impossible: a registry change that
    would let reset delete the user's own files."""
    user_owned = ("Manifest.md", "Defs.lean", "Root.lean", "BRIEF.md")
    for e in satellites.FILE_SATELLITES:
        if e.disposition != satellites.SWEPT:
            continue
        for name in user_owned:
            assert not fnmatch.fnmatch(name, e.pattern), (
                f"swept pattern {e.pattern!r} ({e.scope}) matches "
                f"user-owned {name!r} — reset would destroy user work")


def test_cli_sweeper_reads_the_registry() -> None:
    assert cli.PROOFS_SWEEP_PATTERNS == satellites.swept(
        satellites.SCOPE_PROOFS)


def test_reset_sweeps_exactly_the_registry_and_reports_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
) -> None:
    """Functional pin of the whole contract: one instance of EVERY
    swept entry is deleted; every kept entry survives; an UNCLAIMED
    file is reported by name and NOT deleted."""
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "wilson"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "Manifest.md").write_text("# w\n\n## Statement\n\nTrue\n",
                                      encoding="utf-8")
    (pdir / "Defs.lean").write_text("-- defs\n", encoding="utf-8")
    (pdir / "Root.lean").write_text("-- root\n", encoding="utf-8")
    (pdir / "BRIEF.md").write_text("brief\n", encoding="utf-8")
    # One concrete instance per swept entry.
    concrete = {
        "L_*.lean": "L_x.lean", "_strategy_*.lean": "_strategy_1.lean",
        "new_*.lean": "new_lemma.lean",
        "*.backup": "L_x.lean.backup",
        "*.verify_backup": "L_x.lean.verify_backup",
        "*.verify_backup_s*": "L_x.lean.verify_backup_s7",
        "*.lean.tmp": "L_x.lean.tmp", "*.lean.tmp_s*": "L_x.lean.tmp_s7",
        "_gateway_slot_*.lean": "_gateway_slot_0.lean",
        "_gateway_smoke_*.lean": "_gateway_smoke_1.lean",
        "_axiom_probe_*.lean": "_axiom_probe_1.lean",
    }
    planted: "list[Path]" = []
    for e in satellites.FILE_SATELLITES:
        if e.disposition != satellites.SWEPT:
            continue
        name = concrete.get(e.pattern, e.pattern)
        base = {
            satellites.SCOPE_PROOFS: pdir / "proofs",
            satellites.SCOPE_PROBLEM_ROOT: pdir,
            satellites.SCOPE_RUNTIME_SLOTS:
                tmp_path / ".asterism" / "runtime_slots",
            satellites.SCOPE_WORKSPACE: tmp_path,
        }[e.scope]
        base.mkdir(parents=True, exist_ok=True)
        p = base / name
        if e.is_dir:
            p.mkdir()
            (p / "inner.md").write_text("x", encoding="utf-8")
        else:
            p.write_text("x", encoding="utf-8")
        planted.append(p)
    # …and one file nobody registered.
    stray = pdir / "mystery_artifact.txt"
    stray.write_text("who wrote me?", encoding="utf-8")

    rc = cli.cmd_reset(argparse.Namespace(problem="wilson"))
    out = capsys.readouterr().out
    assert rc == 0, out
    for p in planted:
        assert not p.exists(), f"swept entry survived: {p}"
    for name in ("Manifest.md", "Defs.lean", "Root.lean", "BRIEF.md"):
        assert (pdir / name).exists(), f"kept entry deleted: {name}"
    assert stray.exists(), "complement audit must REPORT, never delete"
    assert "mystery_artifact.txt" in out
    assert "no satellite-registry entry claims" in out
