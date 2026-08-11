"""F55 — postmortem progress-note persistence (Tooling/pipeline/_drafts.py).

Each kind in `PARTIAL_PERSIST` (currently backward + builder) carries
its own per-goal note file. After a timed-out spawn, the framework
runs a short postmortem spawn that writes `_progress.md`; the wrapper
copies it into `.drafts/<kind>_g<gid>.md` for the next spawn.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.pipeline import _drafts


def test_persist_writes_backward_progress(tmp_path: Path) -> None:
    attempts_dir = tmp_path / ".attempts" / "pid-1"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "_progress.md").write_text(
        "Considering Kelly minimiser route, blocked on the foot-of-perp lemma name.",
        encoding="utf-8",
    )
    problem_dir = tmp_path / "Problems" / "sg"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=42,
    )
    assert out is not None
    assert out == problem_dir / ".drafts" / "backward_g42.md"
    body = out.read_text(encoding="utf-8")
    assert "_progress.md" in body
    assert "Kelly minimiser" in body


def test_persist_writes_builder_progress(tmp_path: Path) -> None:
    attempts_dir = tmp_path / ".attempts" / "pid-2"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "_progress.md").write_text(
        "Tried `omega` then `polyrith`; need a divisibility lemma I can't name.",
        encoding="utf-8",
    )
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="builder", goal_id=7,
    )
    assert out is not None
    assert out.name == "builder_g7.md"
    assert "_progress.md" in out.read_text(encoding="utf-8")


def test_persist_no_op_when_source_missing(tmp_path: Path) -> None:
    """No `_progress.md` (postmortem didn't fire / also timed out) →
    no draft written. Common case when the spawn died very early."""
    attempts_dir = tmp_path / ".attempts" / "pid-empty"
    attempts_dir.mkdir(parents=True)
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=1,
    )
    assert out is None
    assert not (problem_dir / ".drafts").exists()


def test_persist_no_op_when_attempts_dir_missing(tmp_path: Path) -> None:
    """Wrapper may call persist on early-exit paths (goal_not_found,
    lean_file_missing) before any spawn touched disk → attempts_dir
    doesn't exist. Must not crash."""
    attempts_dir = tmp_path / ".attempts" / "never-created"
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=1,
    )
    assert out is None
    assert not (problem_dir / ".drafts").exists()


def test_persist_no_op_for_unknown_kind(tmp_path: Path) -> None:
    """Kinds not in PARTIAL_PERSIST (e.g. 'verify') → silent no-op so
    pipeline can call this generically."""
    attempts_dir = tmp_path / ".attempts" / "pid-x"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "_progress.md").write_text("anything", encoding="utf-8")
    problem_dir = tmp_path / "Problems" / "p"
    assert _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="verify", goal_id=1,
    ) is None


def test_persist_truncates_oversize_content(tmp_path: Path) -> None:
    """Long progress notes get capped at PARTIAL_BUDGETS so Context.md
    stays tight. The postmortem prompt targets ~150 words but a poorly-
    behaved agent could overflow; the cap is a hard backstop."""
    attempts_dir = tmp_path / ".attempts" / "pid-big"
    attempts_dir.mkdir(parents=True)
    huge = "x" * (_drafts.PARTIAL_BUDGETS["backward"] + 500)
    (attempts_dir / "_progress.md").write_text(huge, encoding="utf-8")
    problem_dir = tmp_path / "Problems" / "p"
    out = _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=99,
    )
    body = out.read_text(encoding="utf-8")
    assert "truncated" in body
    assert len(body) < len(huge) + 500  # full original NOT in body


def test_persist_idempotent_overwrite(tmp_path: Path) -> None:
    """Two persist calls in a row → most recent content wins. Each
    timeout's postmortem note replaces the prior one; the agent always
    sees the freshest state."""
    problem_dir = tmp_path / "Problems" / "p"
    for content in ("first try", "second try, better"):
        attempts_dir = tmp_path / ".attempts" / f"pid-{content[:5]}"
        attempts_dir.mkdir(parents=True)
        (attempts_dir / "_progress.md").write_text(content, encoding="utf-8")
        _drafts.persist_partials(
            attempts_dir=attempts_dir, problem_dir=problem_dir,
            kind="backward", goal_id=1,
        )
    final = _drafts.read_partial(
        problem_dir=problem_dir, kind="backward", goal_id=1)
    assert "second try, better" in final
    assert "first try" not in final


def test_clear_removes_draft(tmp_path: Path) -> None:
    problem_dir = tmp_path / "Problems" / "p"
    attempts_dir = tmp_path / ".attempts" / "pid-1"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "_progress.md").write_text("note", encoding="utf-8")
    _drafts.persist_partials(
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        kind="backward", goal_id=5,
    )
    assert _drafts.drafts_path(problem_dir, "backward", 5).exists()
    _drafts.clear_partial(
        problem_dir=problem_dir, kind="backward", goal_id=5)
    assert not _drafts.drafts_path(problem_dir, "backward", 5).exists()


def test_clear_no_error_when_missing(tmp_path: Path) -> None:
    """Most pipelines never produce a draft; clear must tolerate that."""
    _drafts.clear_partial(
        problem_dir=tmp_path / "Problems" / "p",
        kind="backward", goal_id=99,
    )  # no exception


def test_per_goal_isolation(tmp_path: Path) -> None:
    """Drafts for different goals don't interfere — drafts_path includes
    the goal id."""
    problem_dir = tmp_path / "Problems" / "p"
    for gid, content in [(1, "g1 note"), (2, "g2 note")]:
        attempts_dir = tmp_path / ".attempts" / f"pid-g{gid}"
        attempts_dir.mkdir(parents=True)
        (attempts_dir / "_progress.md").write_text(content, encoding="utf-8")
        _drafts.persist_partials(
            attempts_dir=attempts_dir, problem_dir=problem_dir,
            kind="backward", goal_id=gid,
        )
    assert "g1 note" in _drafts.read_partial(
        problem_dir=problem_dir, kind="backward", goal_id=1)
    assert "g2 note" in _drafts.read_partial(
        problem_dir=problem_dir, kind="backward", goal_id=2)


def test_per_kind_isolation(tmp_path: Path) -> None:
    """Backward and Builder drafts on the same goal don't collide —
    drafts_path includes the kind."""
    problem_dir = tmp_path / "Problems" / "p"
    # Two separate attempts dirs simulating two timeouts with different notes
    bw_dir = tmp_path / ".attempts" / "pid-bw"
    bw_dir.mkdir(parents=True)
    (bw_dir / "_progress.md").write_text("backward note", encoding="utf-8")
    bd_dir = tmp_path / ".attempts" / "pid-bd"
    bd_dir.mkdir(parents=True)
    (bd_dir / "_progress.md").write_text("builder note", encoding="utf-8")
    _drafts.persist_partials(
        attempts_dir=bw_dir, problem_dir=problem_dir,
        kind="backward", goal_id=10,
    )
    _drafts.persist_partials(
        attempts_dir=bd_dir, problem_dir=problem_dir,
        kind="builder", goal_id=10,
    )
    bk = _drafts.read_partial(
        problem_dir=problem_dir, kind="backward", goal_id=10)
    bd = _drafts.read_partial(
        problem_dir=problem_dir, kind="builder", goal_id=10)
    assert "backward note" in bk and "builder note" not in bk
    assert "builder note" in bd and "backward note" not in bd


# ---------------------------------------------------------------------
# salvage_orphan_patches — startup patch.lean recovery
# ---------------------------------------------------------------------

import sqlite3
from Tooling.state import db


@pytest.fixture
def conn(tmp_path: Path,
         monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at) "
              "VALUES ('p', 'Problems/p/Manifest.md', ?)", (db.now(),))
    c.commit()
    return c


def _seed_goal(conn: sqlite3.Connection, slug: str) -> int:
    return db.insert_goal(
        conn, problem="p", slug=slug,
        lean_path=f"Problems/p/proofs/L_{slug}.lean",
        statement="T", origin="backward",
        depth=1,
    )


def _write_orphan(tmp_path: Path, uuid: str, body: str) -> Path:
    d = tmp_path / ".attempts" / uuid
    d.mkdir(parents=True)
    (d / "patch.lean").write_text(body, encoding="utf-8")
    return d


def test_salvage_persists_substantive_patch(
    tmp_path: Path, conn: sqlite3.Connection,
) -> None:
    """Orphan patch.lean with a real proof body → persisted under
    `.drafts/builder_g<id>_patch.lean`. Next builder spawn reads via
    `read_partial_patch`."""
    gid = _seed_goal(conn, "foo")
    _write_orphan(tmp_path, "abc", (
        "import Mathlib\n"
        "namespace Problems.p\n"
        "theorem foo : True := by\n"
        "  trivial\n"
        "end Problems.p\n"
    ))
    n = _drafts.salvage_orphan_patches(conn, tmp_path)
    assert n == 1
    body = _drafts.read_partial_patch(
        problem_dir=tmp_path / "Problems" / "p",
        kind="builder", goal_id=gid)
    assert body is not None
    assert "theorem foo" in body
    assert "trivial" in body


def test_salvage_skips_sorry_only_stub(
    tmp_path: Path, conn: sqlite3.Connection,
) -> None:
    """A patch.lean that just carries the original `:= by sorry` stub
    is not substantive — surfacing it as a "previous attempt" would
    mislead. Skip."""
    gid = _seed_goal(conn, "bar")
    _write_orphan(tmp_path, "abc", (
        "import Mathlib\n"
        "namespace Problems.p\n"
        "theorem bar : True := by sorry\n"
        "end Problems.p\n"
    ))
    n = _drafts.salvage_orphan_patches(conn, tmp_path)
    assert n == 0
    body = _drafts.read_partial_patch(
        problem_dir=tmp_path / "Problems" / "p",
        kind="builder", goal_id=gid)
    assert body is None


def test_salvage_skips_unknown_slug(
    tmp_path: Path, conn: sqlite3.Connection,
) -> None:
    """Patch with a theorem name that isn't in the DB (slug was
    deleted by reset / pruned / never landed) — skip, no draft
    written. Log only."""
    _seed_goal(conn, "real_one")
    _write_orphan(tmp_path, "abc", (
        "theorem ghost_slug : True := by trivial\n"
    ))
    n = _drafts.salvage_orphan_patches(conn, tmp_path)
    assert n == 0


def test_salvage_no_attempts_dir(
    tmp_path: Path, conn: sqlite3.Connection,
) -> None:
    """No `.attempts/` dir → 0 salvaged, no error."""
    _seed_goal(conn, "foo")
    assert _drafts.salvage_orphan_patches(conn, tmp_path) == 0


def test_salvage_keeps_an_oversize_patch_whole(
    tmp_path: Path, conn: sqlite3.Connection,
) -> None:
    """The salvaged patch is a FILE, and the attempts dir it came from
    is deleted right after — so a tail cut here destroyed proof the
    framework was holding, permanently, to bound a surface it does not
    live on. Context.md pays for what it inlines; this slot pays for
    nothing (2026-08-11)."""
    gid = _seed_goal(conn, "big")
    body = (
        "theorem big : True := by\n"
        + "  -- " + "x" * 20_000 + "\n"
        + "  trivial\n"
    )
    _write_orphan(tmp_path, "abc", body)
    n = _drafts.salvage_orphan_patches(conn, tmp_path)
    assert n == 1
    saved = _drafts.read_partial_patch(
        problem_dir=tmp_path / "Problems" / "p",
        kind="builder", goal_id=gid)
    assert saved is not None
    assert "truncated" not in saved
    assert saved.strip() == body.strip()


def test_clear_partial_patch_drops_drafts(
    tmp_path: Path, conn: sqlite3.Connection,
) -> None:
    """Pipeline success → clear salvaged patch."""
    gid = _seed_goal(conn, "ok")
    _write_orphan(tmp_path, "abc", (
        "theorem ok : True := by trivial\n"
    ))
    _drafts.salvage_orphan_patches(conn, tmp_path)
    pdir = tmp_path / "Problems" / "p"
    assert _drafts.read_partial_patch(
        problem_dir=pdir, kind="builder", goal_id=gid) is not None
    _drafts.clear_partial_patch(problem_dir=pdir, kind="builder",
                                goal_id=gid)
    assert _drafts.read_partial_patch(
        problem_dir=pdir, kind="builder", goal_id=gid) is None


# ---------------------------------------------------------------------
# Strategist plan note — private cross-wake memory (2026-07-05)
# ---------------------------------------------------------------------

def test_plan_note_persist_and_read_roundtrip(tmp_path):
    from Tooling.pipeline import _drafts
    problem_dir = tmp_path / "Problems" / "p"
    attempts = tmp_path / ".attempts" / "x"
    attempts.mkdir(parents=True)
    problem_dir.mkdir(parents=True)
    (attempts / "_plan.md").write_text("plan v1", encoding="utf-8")
    n = _drafts.persist_plan_note(problem_dir=problem_dir,
                                  attempts_dir=attempts)
    assert n == len("plan v1")
    assert _drafts.read_plan_note(problem_dir) == "plan v1"
    # REWRITE contract: a later persist fully replaces the note.
    (attempts / "_plan.md").write_text("v2", encoding="utf-8")
    _drafts.persist_plan_note(problem_dir=problem_dir, attempts_dir=attempts)
    assert _drafts.read_plan_note(problem_dir) == "v2"


def test_plan_note_absent_means_no_update(tmp_path):
    from Tooling.pipeline import _drafts
    problem_dir = tmp_path / "Problems" / "p"
    (problem_dir / ".drafts").mkdir(parents=True)
    _drafts.plan_note_path(problem_dir).write_text("keep me",
                                                   encoding="utf-8")
    attempts = tmp_path / ".attempts" / "y"
    attempts.mkdir(parents=True)
    assert _drafts.persist_plan_note(problem_dir=problem_dir,
                                     attempts_dir=attempts) is None
    assert _drafts.read_plan_note(problem_dir) == "keep me"


# ---------------------------------------------------------------------
# salvage_patch_fallback — in-daemon timeout last resort (2026-07-06,
# user ruling): the postmortem note is the preferred carry-over (it
# demands an ALTER plan, steering the next spawn away from the dead
# end); the half-finished patch is saved ONLY when even the postmortem
# left nothing.
# ---------------------------------------------------------------------

def _mk_dirs(tmp_path):
    attempts = tmp_path / ".attempts" / "x"
    problem_dir = tmp_path / "Problems" / "p"
    attempts.mkdir(parents=True)
    problem_dir.mkdir(parents=True)
    return attempts, problem_dir


def test_salvage_patch_fallback_saves_substantive_patch(tmp_path):
    from Tooling.pipeline import _drafts
    attempts, problem_dir = _mk_dirs(tmp_path)
    (attempts / "patch.lean").write_text(
        "import Mathlib\n"
        "theorem s9 : True := by\n"
        "  have h1 : 1 + 1 = 2 := rfl\n"
        "  exact trivial\n", encoding="utf-8")
    out = _drafts.salvage_patch_fallback(
        attempts_dir=attempts, problem_dir=problem_dir,
        kind="builder", goal_id=7)
    assert out is not None and out.exists()
    assert out == _drafts.patch_drafts_path(problem_dir, "builder", 7)
    assert "have h1" in out.read_text(encoding="utf-8")


def test_salvage_patch_fallback_skips_bare_sorry_stub(tmp_path):
    """A pristine skeleton is not a clue - surfacing it as a previous
    attempt would mislead (same guard as the startup orphan salvage)."""
    from Tooling.pipeline import _drafts
    attempts, problem_dir = _mk_dirs(tmp_path)
    (attempts / "patch.lean").write_text(
        "import Mathlib\nnamespace P\n"
        "theorem s9 : True := by sorry\nend P\n", encoding="utf-8")
    assert _drafts.salvage_patch_fallback(
        attempts_dir=attempts, problem_dir=problem_dir,
        kind="builder", goal_id=7) is None
    assert not _drafts.patch_drafts_path(problem_dir, "builder", 7).exists()


def test_salvage_patch_fallback_missing_patch_or_kind(tmp_path):
    from Tooling.pipeline import _drafts
    attempts, problem_dir = _mk_dirs(tmp_path)
    assert _drafts.salvage_patch_fallback(
        attempts_dir=attempts, problem_dir=problem_dir,
        kind="builder", goal_id=7) is None
    (attempts / "patch.lean").write_text(
        "theorem s9 : True := trivial\n", encoding="utf-8")
    assert _drafts.salvage_patch_fallback(
        attempts_dir=attempts, problem_dir=problem_dir,
        kind="strategist", goal_id=7) is None


def test_prior_patch_section_surfaces_for_backward_with_caveat(tmp_path):
    """The salvaged-patch Context section now renders for Backward too;
    its patch declares the PRIOR strategy s<id>, so the section carries
    the do-not-copy-the-header caveat."""
    from Tooling.pipeline import _drafts
    from Tooling.agent import context as ctx
    problem_dir = tmp_path / "Problems" / "p"
    (problem_dir / ".drafts").mkdir(parents=True)
    _drafts.patch_drafts_path(problem_dir, "backward", 5).write_text(
        "theorem s4 : True := by\n  exact trivial\n", encoding="utf-8")
    lines = ctx._section_prior_patch("backward", problem_dir, 5)
    text = "\n".join(lines)
    assert "previous patch.lean attempt" in text
    assert "NEW one" in text                       # the s<id> caveat
    # Builder rendering unchanged: no caveat line.
    _drafts.patch_drafts_path(problem_dir, "builder", 5).write_text(
        "theorem b : True := by\n  exact trivial\n", encoding="utf-8")
    btext = "\n".join(ctx._section_prior_patch("builder", problem_dir, 5))
    assert "NEW one" not in btext
