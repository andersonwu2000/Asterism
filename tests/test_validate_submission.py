"""validate_file commit-gate mirror (#8 / P2).

Three classes of `validate_file ok:true → commit rejects/false-fails` that
each cost a full retry round, now surfaced pre-commit:
  (c) opens — the candidate elaborates against the session patch's own
      `open` lines, not just Defs.lean's (`_harvest_open_lines`/`_merge_opens`);
  (b) citation-eligibility — `submission.citation` mirrors the commit gate
      via the shared `db.classify_cited_slug` SoT;
  (a) annotation — `submission.annotation` mirrors the `agent_no_annotation`
      gate (leading `--` comment block on a real patch).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.lsp import gateway as gw
from Tooling.state import db


# ---------------------------------------------------------------------
# (c) opens — pure helpers
# ---------------------------------------------------------------------

def test_harvest_open_lines_keeps_file_scope_excludes_scoped_in():
    text = (
        "import Mathlib\n"
        "open MeasureTheory\n"
        "  open scoped Topology  \n"
        "open Foo in\n"            # scope-limited form — excluded
        "theorem t : True := trivial\n"
    )
    assert gw._harvest_open_lines(text) == [
        "open MeasureTheory", "open scoped Topology"]


def test_merge_opens_normalizes_dedups_and_drops_content_present():
    # defs_opens are raw args; extra_opens are full lines; content already
    # opens MeasureTheory so it must NOT be re-emitted in the prefix.
    content = "open MeasureTheory\ntheorem t : True := trivial\n"
    out = gw._merge_opens(
        content,
        defs_opens=["MeasureTheory", "BigOperators"],
        extra_opens=["open scoped Topology", "open BigOperators"],
    )
    assert out == ["open BigOperators", "open scoped Topology"]


# ---------------------------------------------------------------------
# (a) annotation — pure helper
# ---------------------------------------------------------------------

def test_annotation_skips_sorry_stub():
    assert gw._annotation_submission(
        "theorem foo : True := by sorry")["checked"] is False


def test_annotation_skips_non_theorem():
    assert gw._annotation_submission("def foo := 1")["checked"] is False


def test_annotation_flags_missing_comment_on_real_patch():
    r = gw._annotation_submission("theorem foo : True := by\n  trivial\n")
    assert r["checked"] is True and r["ok"] is False and r["note"]


def test_annotation_passes_with_leading_comment():
    r = gw._annotation_submission(
        "-- strategy: close by trivial\ntheorem foo : True := by\n  trivial\n")
    assert r["checked"] is True and r["ok"] is True and r["note"] == ""


# ---------------------------------------------------------------------
# (b) citation — shared SoT + gateway submission
# ---------------------------------------------------------------------

@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)", (db.now(),))
    c.commit()
    c.close()
    return tmp_path


def _goal(slug: str, *, status: str) -> int:
    c = db.connect()
    gid = db.insert_goal(
        c, problem="p", slug=slug,
        lean_path=f"Problems/p/proofs/L_{slug}.lean",
        statement="T", origin="backward", status=status)
    c.commit()
    c.close()
    return gid


def _orphan_file(ws: Path, slug: str):
    p = ws / "Problems" / "p" / "proofs" / f"L_{slug}.lean"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("theorem L_x : True := by sorry\n", encoding="utf-8")


def test_classify_cited_slug_statuses(ws: Path):
    _goal("done", status="proved")
    _goal("wip", status="open")
    c = db.connect()
    assert db.classify_cited_slug(
        c, problem="p", slug="done", workspace=ws)[1] == "proved"
    assert db.classify_cited_slug(
        c, problem="p", slug="wip", workspace=ws)[1] == "open"
    # no goal, no file → untracked (None, orphan False)
    assert db.classify_cited_slug(
        c, problem="p", slug="ghost", workspace=ws) == (None, None, False)
    c.close()


def test_classify_cited_slug_orphan(ws: Path):
    _orphan_file(ws, "stale")            # file on disk, no goal row
    c = db.connect()
    gid, status, orphan = db.classify_cited_slug(
        c, problem="p", slug="stale", workspace=ws)
    c.close()
    assert gid is None and status is None and orphan is True


def _cite(slug: str) -> str:
    return f"import Problems.p.proofs.L_{slug}\ntheorem s1 : True := trivial\n"


def test_citation_proved_is_clean(ws: Path):
    _goal("done", status="proved")
    r = gw._citation_submission(_cite("done"), "p", ws, declared=set())
    assert r == {"ok": True, "issues": []}


def test_citation_open_is_warn_not_error(ws: Path):
    _goal("wip", status="open")
    r = gw._citation_submission(_cite("wip"), "p", ws, declared=set())
    assert r["ok"] is True                       # warn does not fail ok
    assert r["issues"][0]["severity"] == "warn"
    assert r["issues"][0]["status"] == "open"


def test_citation_dead_is_error(ws: Path):
    _goal("bad", status="dead")
    r = gw._citation_submission(_cite("bad"), "p", ws, declared=set())
    assert r["ok"] is False
    assert r["issues"][0]["severity"] == "error"


def test_citation_orphan_is_error(ws: Path):
    _orphan_file(ws, "stale")
    r = gw._citation_submission(_cite("stale"), "p", ws, declared=set())
    assert r["ok"] is False
    assert r["issues"][0]["status"] == "orphan"


def test_citation_declared_sibling_skipped(ws: Path):
    # cited slug is a declared (inlined) sibling stub this call → legit.
    r = gw._citation_submission(_cite("helper"), "p", ws, declared={"helper"})
    assert r == {"ok": True, "issues": []}


def test_citation_other_problem_import_ignored(ws: Path):
    content = "import Problems.other.proofs.L_x\ntheorem s1 : True := trivial\n"
    r = gw._citation_submission(content, "p", ws, declared=set())
    assert r == {"ok": True, "issues": []}


def test_citation_untracked_typo_passes_through(ws: Path):
    # no goal, no file → lake's unknown-identifier covers it, no submission issue
    r = gw._citation_submission(_cite("ghost"), "p", ws, declared=set())
    assert r == {"ok": True, "issues": []}
