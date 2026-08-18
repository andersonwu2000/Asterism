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


def test_annotation_checks_def_patch():
    """A data goal's final patch is a `def` — commit's annotation gate
    applies to it exactly like a theorem, and the mirror used to skip it
    with an unexplained `checked: false` (feedback family). Now checked:
    a bare def flags, an annotated one passes."""
    r = gw._annotation_submission("noncomputable def foo : Nat := 1")
    assert r["checked"] is True and r["ok"] is False and r["note"]
    r2 = gw._annotation_submission(
        "-- strategy: literal value\nnoncomputable def foo : Nat := 1")
    assert r2["checked"] is True and r2["ok"] is True


def test_annotation_skips_declless_probe():
    assert gw._annotation_submission(
        "import Mathlib\nopen Real\n")["checked"] is False


def test_annotation_flags_missing_comment_on_real_patch():
    r = gw._annotation_submission("theorem foo : True := by\n  trivial\n")
    assert r["checked"] is True and r["ok"] is False and r["note"]


def test_annotation_passes_with_leading_comment():
    r = gw._annotation_submission(
        "-- strategy: close by trivial\ntheorem foo : True := by\n  trivial\n")
    assert r["checked"] is True and r["ok"] is True and r["note"] == ""


def test_annotation_skips_the_mint_arm():
    """07-29 feedback + the 07-30 rationale retirement: mint commits have
    no annotation gate, so nagging every mint probe for a leading comment
    states a requirement that no longer exists."""
    body = "theorem foo : True := by\n  trivial\n"
    assert gw._annotation_submission(body)["checked"] is True
    r = gw._annotation_submission(body, is_mint=True)
    assert r["checked"] is False and "no annotation" in r["note"]


# ---------------------------------------------------------------------
# repeated-diagnostic collapse (07-29 feedback: 3 identical push_neg
# deprecation warnings on every probe drowned the real signal)
# ---------------------------------------------------------------------

def test_collapse_repeats_folds_identical_messages_only():
    diags = [
        {"line": 3, "col": 2, "severity": "warning", "message": "push_neg dep"},
        {"line": 9, "col": 2, "severity": "warning", "message": "push_neg dep"},
        {"line": 12, "col": 0, "severity": "warning", "message": "push_neg dep"},
        {"line": 5, "col": 1, "severity": "error", "message": "unknown id"},
    ]
    out = gw._collapse_repeats(diags)
    assert len(out) == 2
    first = out[0]
    assert first["line"] == 3 and first["repeats"] == 3
    assert first["also_lines"] == [9, 12]
    assert out[1]["message"] == "unknown id" and "repeats" not in out[1]


def test_collapse_repeats_keeps_distinct_messages():
    diags = [
        {"line": 1, "col": 0, "severity": "error", "message": "a"},
        {"line": 2, "col": 0, "severity": "error", "message": "b"},
    ]
    assert gw._collapse_repeats(diags) == diags


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
        "INSERT INTO problems (name, created_at)"
        " VALUES ('p', ?)", (db.now(),))
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


def test_citation_open_kind_aware_severity(ws: Path):
    """Pipeline-accurate mirror: only a Backward decomposition can legally
    cite an open sibling (commit auto-links it). For Builder/Forward the
    citation dies at their axiom gate, so the mirror reports the ERROR it
    is — the historical one-size warn taught agents to ignore it and burn
    the commit round (feedback family)."""
    _goal("wip", status="open")
    for k in ("builder", "forward"):
        r = gw._citation_submission(_cite("wip"), "p", ws,
                                    declared=set(), kind=k)
        assert r["ok"] is False, k
        assert r["issues"][0]["severity"] == "error", k
    # Backward (and a kind-less legacy client) keep the warn.
    for k in ("backward", None):
        r = gw._citation_submission(_cite("wip"), "p", ws,
                                    declared=set(), kind=k)
        assert r["ok"] is True, k
        assert r["issues"][0]["severity"] == "warn", k


def test_citation_stub_count_does_not_change_verdict(ws: Path):
    """Task #123: citation permission is no longer keyed on whether the
    patch declares stubs — commit auto-links a cited unproved sibling
    either way (the WAIT edge is what defers verification, not the stub).
    The mirror must therefore give the same auto-link warn for a sorry-free
    stub-less pure-cite as for a decomposition; the old P4 escalation to
    `error` now predicts a rejection that no longer happens."""
    _goal("wip", status="open")
    for content in (_cite("wip"), _cite("wip").replace("trivial", "by sorry")):
        for k in ("backward", "formalizer", None):
            r = gw._citation_submission(content, "p", ws,
                                        declared=set(), kind=k)
            assert r["ok"] is True, (k, content)
            assert r["issues"][0]["severity"] == "warn", (k, content)
            assert "auto-links" in r["issues"][0]["hint"]


def test_citation_hard_terminal_error_regardless_of_kind(ws: Path):
    _goal("bad2", status="disproved")
    r = gw._citation_submission(_cite("bad2"), "p", ws,
                                declared=set(), kind="backward")
    assert r["ok"] is False and r["issues"][0]["severity"] == "error"


def test_register_body_carries_pipeline_kind(tmp_path, monkeypatch):
    """The client side of the kind-aware mirror: `_write_mcp_config`'s
    /register body includes the pipeline kind so SessionMetadata.kind is
    populated (validate_file passes it to the citation mirror)."""
    import json as _json
    import urllib.request as _u
    from Tooling import pipeline as pl
    seen: dict = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"session_token": "tok-kind"}'

    def fake_urlopen(req, timeout=None):
        url = getattr(req, "full_url", str(req))
        if url.endswith("/register"):
            seen.update(_json.loads(req.data.decode("utf-8")))
        return _Resp()
    monkeypatch.setattr(_u, "urlopen", fake_urlopen)
    adir = tmp_path / ".attempts" / "x"
    adir.mkdir(parents=True)
    target = tmp_path / "t.lean"
    target.write_text("-- t\n", encoding="utf-8")
    pl._write_mcp_config(adir, tmp_path, target,
                         pipeline_id="pid-1", problem="p", kind="builder")
    assert seen.get("kind") == "builder"


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

def test_split_visibility_only_flags_cycles(tmp_path):
    """2026-07-10 (task #84): plain cross-references are no longer the
    agent's problem — commit injects the intra-batch import edges
    mechanically. Only CYCLES (no module import order exists) remain."""
    from Tooling.state import assemble
    stubs = {
        "iso_inf": "namespace P\ntheorem iso_inf : True := by sorry\nend P\n",
        "comm_left": ("namespace P\n"
                      "theorem comm_left : True := iso_inf.elim\n"
                      "end P\n"),
    }
    # acyclic reference → framework injects at commit, no issue
    assert assemble.split_visibility_issues(stubs, problem="p") == []
    # a mention in a comment is not a reference
    stubs["comm_left"] = ("namespace P\n-- see iso_inf for the idea\n"
                          "theorem comm_left : True := trivial\nend P\n")
    assert assemble.split_visibility_issues(stubs, problem="p") == []
    # mutual reference = cycle → error with the restructure hint
    stubs["comm_left"] = ("namespace P\n"
                          "theorem comm_left : True := iso_inf.elim\n"
                          "end P\n")
    stubs["iso_inf"] = ("namespace P\n"
                        "theorem iso_inf : True := comm_left.elim\n"
                        "end P\n")
    issues = assemble.split_visibility_issues(stubs, problem="p")
    assert len(issues) == 1
    assert "cycle" in issues[0]["hint"]
    assert set(issues[0]["cycle"][:2]) <= {"iso_inf", "comm_left"}


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
