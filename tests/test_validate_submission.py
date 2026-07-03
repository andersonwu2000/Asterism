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
# (a2) decl-head slug — snake_case gate surfaced pre-commit (green #69/#107)
# ---------------------------------------------------------------------

def test_declhead_flags_camelcase_slug():
    r = gw._declhead_submission(
        "noncomputable def diskCompactSpace : True := trivial")
    assert r["checked"] is True and r["ok"] is False
    assert "diskCompactSpace" in r["bad_slugs"]


def test_declhead_passes_snake_case():
    r = gw._declhead_submission(
        "theorem disk_compact_space : True := by trivial")
    assert r["checked"] is True and r["ok"] is True


def test_declhead_unchecked_when_no_decl():
    r = gw._declhead_submission("import Mathlib\nopen Real\n")
    assert r["checked"] is False and r["ok"] is True


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


# ---------------------------------------------------------------------
# D-lite (task #5): deterministic commit-policy predictions the single-
# unit elaboration structurally cannot surface.
# ---------------------------------------------------------------------

def test_split_visibility_flags_stub_to_stub_reference(tmp_path):
    from Tooling.state import assemble
    stubs = {
        "iso_inf": "namespace P\ntheorem iso_inf : True := by sorry\nend P\n",
        "comm_left": ("namespace P\n"
                      "theorem comm_left : True := iso_inf.elim\n"
                      "end P\n"),
    }
    issues = assemble.split_visibility_issues(stubs, problem="p")
    assert len(issues) == 1
    assert issues[0]["file"] == "new_comm_left.lean"
    assert issues[0]["references"] == "iso_inf"
    # hand-written import silences it (the framework honors it at commit)
    stubs["comm_left"] = ("import Problems.p.proofs.L_iso_inf\n"
                          + stubs["comm_left"])
    assert assemble.split_visibility_issues(stubs, problem="p") == []
    # a mention in a comment is not a reference
    stubs["comm_left"] = ("namespace P\n-- see iso_inf for the idea\n"
                          "theorem comm_left : True := trivial\nend P\n")
    assert assemble.split_visibility_issues(stubs, problem="p") == []


def test_locked_signature_submission(tmp_path):
    from Tooling.lsp import gateway
    att = tmp_path / "att"
    att.mkdir()
    locked = "theorem s42 (n : Nat) : n = n"
    (att / "_locked_signature.txt").write_text(locked, encoding="utf-8")
    # untouched signature → ok
    good = "theorem s42 (n : Nat) : n = n := by rfl\n"
    r = gateway._locked_signature_submission(good, att)
    assert r == {"checked": True, "ok": True}
    # edited binder → not ok, carries locked + current
    bad = "theorem s42 (m : Nat) : m = m := by rfl\n"
    r = gateway._locked_signature_submission(bad, att)
    assert r["checked"] and not r["ok"]
    assert r["locked"] == locked
    # content that never mentions s42 (a sub-goal stub probe) → None
    assert gateway._locked_signature_submission(
        "theorem sub : True := by sorry\n", att) is None
    # no seed file (non-Backward session) → None
    (att / "_locked_signature.txt").unlink()
    assert gateway._locked_signature_submission(good, att) is None


def test_stale_olean_submission(tmp_path):
    import os
    import time
    from Tooling.lsp import gateway
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    src = proofs / "L_helper.lean"
    src.write_text("theorem helper : True := trivial\n", encoding="utf-8")
    olean = (tmp_path / ".lake" / "build" / "lib" / "lean"
             / "Problems" / "p" / "proofs" / "L_helper.olean")
    olean.parent.mkdir(parents=True)
    content = "import Problems.p.proofs.L_helper\n"
    # olean missing → stale
    r = gateway._stale_olean_submission(content, "p", tmp_path)
    assert not r["ok"] and r["issues"][0]["slug"] == "helper"
    # olean fresh (newer than source) → ok
    olean.write_bytes(b"x")
    now = time.time()
    os.utime(src, (now - 100, now - 100))
    os.utime(olean, (now, now))
    r = gateway._stale_olean_submission(content, "p", tmp_path)
    assert r["ok"] and r["issues"] == []
    # olean older than source → stale again
    os.utime(olean, (now - 200, now - 200))
    r = gateway._stale_olean_submission(content, "p", tmp_path)
    assert not r["ok"]
    # no citations at all → None
    assert gateway._stale_olean_submission("theorem t : True := trivial\n",
                                           "p", tmp_path) is None


def test_collect_sibling_stubs_transitive(tmp_path):
    from Tooling.lsp import gateway
    att = tmp_path / "att"
    att.mkdir()
    # content references only `a`; `a` references `b` — fixpoint pulls both
    (att / "new_a.lean").write_text(
        "theorem a : True := b.elim\n", encoding="utf-8")
    (att / "new_b.lean").write_text(
        "theorem b : True := by sorry\n", encoding="utf-8")
    content = "theorem s1 : True := a.elim\n"
    got = gateway._collect_referenced_sibling_stubs(att, content)
    assert {s for s, _ in got} == {"a", "b"}
