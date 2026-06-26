"""Antipattern ingest from failure sources (Phase 12 step 1b)."""
import sqlite3

import pytest

from Tooling.state import db, kb_ingest

NOTE = """### _progress.md
```
## Proof approach
Assemble from Library X via Y.

## Specific blocker
DFinsupp.basis repr has no simp lemmas; unfold got stuck.

## Alternative direction
Skip it, use Basis.ofIsInternal instead.
```
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('P', 'P/Manifest.md', ?)", (db.now(),))
    c.commit()
    return c


def _seed_goal(c, gid):
    c.execute(
        "INSERT INTO goals (id, problem, slug, lean_path, statement, origin,"
        " status, created_at, updated_at)"
        " VALUES (?, 'P', ?, ?, 'True', 'root', 'open', ?, ?)",
        (gid, f"s{gid}", f"P/proofs/L_s{gid}.lean", db.now(), db.now()))
    c.commit()


# --- parser units --------------------------------------------------------- #

def test_drafts_antipattern_extracts_blocker_only():
    res = kb_ingest._drafts_antipattern(NOTE)
    assert res is not None
    title, body = res
    assert "DFinsupp.basis repr has no simp lemmas" in title
    assert body.startswith("Approach:")
    assert "Blocker:" in body
    assert "Basis.ofIsInternal" not in body  # alternative is NOT ingested


def test_drafts_no_blocker_returns_none():
    assert kb_ingest._drafts_antipattern(
        "## Approach\njust an approach, no wall hit\n") is None


def test_clean_decline_strips_comment_prefix_and_directive():
    md = ("-- decline: shelve\n"
          "-- ## The keystone is the WRONG statement\n"
          "-- it is FALSE for an interior center")
    title, body = kb_ingest._clean_decline(md)
    assert title == "The keystone is the WRONG statement"
    assert "decline:" not in body
    assert "FALSE for an interior center" in body


def test_noop_diagnosis_prefers_diagnosis_line():
    detail = ("Batch 00e9 fully resolved with no actionable residue. (1) Meta: "
              "the generic-c0 keystone is the WRONG statement: bdry_point is "
              "FALSE for an interior c0.")
    res = kb_ingest._noop_diagnosis(detail)
    assert res is not None
    title, body = res
    assert "WRONG statement" in title          # diagnosis line, not the meta head
    assert body == detail.strip()


def test_noop_diagnosis_skips_operational_narration():
    assert kb_ingest._noop_diagnosis(
        "Routine tick. Root main (2116) has via s10404 (proposed); all fine.") is None


def test_clean_decline_skips_generic_section_label():
    md = ("-- decline: unprovable\n-- ## Counterexample\n"
          "-- The map f is not injective at 0, so the stated claim fails.")
    title, _ = kb_ingest._clean_decline(md)
    assert title.startswith("The map f is not injective")  # not "Counterexample"


def test_stuck_blocker_extracts_inline_error():
    detail = ("subprocess timeout; stage2 parse: reason=lake_build_error "
              "detail=line 20:15 error: rewrite failed: pattern not found; "
              "stage3 ...")
    res = kb_ingest._stuck_blocker(detail)
    assert res is not None
    title, _ = res
    assert "rewrite failed: pattern not found" in title


# --- end to end ----------------------------------------------------------- #

def test_ingest_end_to_end_idempotent(conn, tmp_path):
    _seed_goal(conn, 7)
    dd = db.problem_dir(tmp_path, "P") / ".drafts"
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "builder_g7.md").write_text(NOTE, encoding="utf-8")

    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('pl1','Builder','7','Goal','failed','agent_shelved', ?, ?)",
        (db.now(), db.now()))
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, proposal_md, ts)"
        " VALUES (7, 'Goal', 'pl1', 'agent_shelved', 'x',"
        " '-- decline: shelve\n-- ## missing keystone blocks any split', ?)",
        (db.now(),))
    conn.commit()

    n1 = kb_ingest.ingest_antipatterns(conn, tmp_path)
    assert n1 == 2  # 1 drafts blocker + 1 decline rationale
    rows = conn.execute(
        "SELECT * FROM kb_entries WHERE type = 'antipattern'").fetchall()
    assert len(rows) == 2
    assert all(r["node_id"] == 7 and r["scope"] == "node" for r in rows)

    # re-run re-converges (drop ingest:* then re-insert) — not 4
    assert kb_ingest.ingest_antipatterns(conn, tmp_path) == 2
    assert conn.execute(
        "SELECT COUNT(*) FROM kb_entries WHERE type = 'antipattern'"
    ).fetchone()[0] == 2


def test_ingest_skips_stale_gid(conn, tmp_path):
    # a .drafts note whose goal id no longer exists → skipped, not crashed
    dd = db.problem_dir(tmp_path, "P") / ".drafts"
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "builder_g999.md").write_text(NOTE, encoding="utf-8")
    assert kb_ingest.ingest_antipatterns(conn, tmp_path) == 0
