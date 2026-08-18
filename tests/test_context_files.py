"""F26 — companion reference files (PAST_DIRECT_ATTEMPTS.md / PAST_VERIFY_FAILURES.md)
+ context._digest_failure helper. Tests cover digest extraction across
all failure_reason kinds and the lazy-load size discipline."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from Tooling.agent import context_files
from Tooling.state import db
from Tooling.agent.context import (
    _ago,
    _digest_failure,
    _section_goal_history,
    compile_context,
)
from Tooling.state.intent import ProblemIntent


# ---------------------------------------------------------------------
# _digest_failure — pure helper covering each failure_reason
# ---------------------------------------------------------------------

def test_digest_lake_build_error_skips_lean_path_dump() -> None:
    """The dominant pre-F26 regression: failure_detail starts with a
    LEAN_PATH dump pushing the actual error past the 1000-char slice
    that agent.py was using. Digest must skip lake-trace lines and
    surface the FIRST real `error:` message."""
    detail = (
        "✖ [8369/8369] Building Problems.compactness.proofs.L_xxx (17s)\n"
        "trace: .> LEAN_PATH=D:\\Asterism\\.lake\\packages\\Cli;...\n"
        "error: Problems/x.lean:7:2: Type mismatch on `ZMod.val_natCast`\n"
        "error: Lean exited with code 1\n"
    )
    out = _digest_failure("lake_build_error", detail)
    assert "Type mismatch" in out
    assert "ZMod.val_natCast" in out
    # Must not be the LEAN_PATH dump
    assert "LEAN_PATH" not in out
    assert "lake/packages" not in out


def test_digest_lake_build_error_strips_file_line_prefix() -> None:
    """Best-effort prefix strip: ` Problems/x.lean:7:2: error: <msg>`
    digest captures `<msg>` without the file:line:col jumble."""
    detail = "error: Problems/x.lean:7:2: Type mismatch in `f`"
    out = _digest_failure("lake_build_error", detail)
    # Must include the meaningful tail
    assert "Type mismatch" in out


def test_digest_agent_timeout_short_circuits() -> None:
    """Already short — no extraction needed, just truncate to cap."""
    out = _digest_failure("agent_timeout", "claude rc=124")
    assert "claude rc=124" in out


def test_digest_forbidden_lemma_short_circuits() -> None:
    out = _digest_failure("forbidden_lemma", "ZMod.wilsons_lemma")
    assert "ZMod.wilsons_lemma" in out


def test_digest_naming_violation_short_circuits() -> None:
    out = _digest_failure(
        "naming_violation",
        "sub-goal slug '1bad' must match [a-z][a-z0-9_]* "
        "(lowercase ascii start, then ascii/digits/underscore)",
    )
    assert "naming_violation" not in out  # we only return the detail
    assert "must match" in out


def test_digest_empty_returns_empty() -> None:
    assert _digest_failure("lake_build_error", "") == ""
    assert _digest_failure("agent_rc_nonzero", "") == ""


def test_digest_lake_build_error_caps_length() -> None:
    """Long error messages get truncated to a sane bound for the
    1-line summary (200 chars)."""
    long = "error: " + "x" * 500
    out = _digest_failure("lake_build_error", long)
    assert len(out) <= 200


# ---------------------------------------------------------------------
# _ago — relative-time renderer
# ---------------------------------------------------------------------

def test_ago_minutes() -> None:
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert "min ago" in _ago(past.isoformat())


def test_ago_hours() -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    assert "h ago" in _ago(past.isoformat())


def test_ago_seconds() -> None:
    past = datetime.now(timezone.utc) - timedelta(seconds=30)
    assert "s ago" in _ago(past.isoformat())


def test_ago_handles_invalid_input() -> None:
    assert _ago(None) == ""
    assert _ago("not-a-timestamp") == ""


# ---------------------------------------------------------------------
# context_files writers
# ---------------------------------------------------------------------

def _row(**kw):
    """Mimic sqlite3.Row's dict-style access for tests."""
    class _Row:
        def __init__(self, **kw):
            self._d = kw
        def __getitem__(self, k): return self._d[k]
        def keys(self): return self._d.keys()
    return _Row(**kw)


def test_write_past_attempts_creates_file_with_full_content(
    tmp_path: Path,
) -> None:
    deads = [
        _row(pipeline_id="pid-1234567890ab", failure_reason="lake_build_error",
             failure_detail="error: Type mismatch on X",
             proposal_md="## My strategy\nUse foo"),
        _row(pipeline_id="pid-2345678901bc", failure_reason="agent_timeout",
             failure_detail="claude rc=124", proposal_md=""),
    ]
    out = context_files.write_past_attempts(deads, tmp_path)
    assert out is not None
    text = out.read_text(encoding="utf-8")
    # Full failure_detail (NOT just digest) lives here
    assert "Type mismatch on X" in text
    assert "My strategy" in text
    assert "claude rc=124" in text
    assert "lake_build_error" in text
    assert "agent_timeout" in text


def test_past_attempts_surface_the_agents_own_note(tmp_path: Path) -> None:
    """2026-08-04 operator finding: the failure history carried only
    framework autopsies — the dying agent's `_progress.md` was already
    preserved verbatim in dead_attempts.artifacts but never rendered,
    so its voice reached only the NEXT attempt (overwrite-only drafts
    slot) and vanished from history. The lazy companion must show it;
    rows without artifacts (legacy) must not crash."""
    import json as _json
    deads = [
        _row(pipeline_id="pid-1234567890ab", failure_reason="agent_timeout",
             failure_detail="rc=124 salvage parse ...", proposal_md="",
             artifacts=_json.dumps({
                 "_progress.md": "converging on gcd descent; blocked on "
                                 "ReflTransGen.lift start-point simp",
                 "patch.lean": "-- half proof"})),
        _row(pipeline_id="pid-2345678901bc", failure_reason="agent_timeout",
             failure_detail="rc=124", proposal_md=""),   # no artifacts key
    ]
    out = context_files.write_past_attempts(deads, tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "blocked on ReflTransGen.lift start-point simp" in text
    assert "Agent note" in text
    assert "half proof" not in text        # only the note, not every artifact


def test_write_past_attempts_empty_returns_none(tmp_path: Path) -> None:
    """No deads → no file written, no clutter."""
    assert context_files.write_past_attempts([], tmp_path) is None
    assert not (tmp_path / "PAST_DIRECT_ATTEMPTS.md").exists()


def test_write_past_backward_creates_file(tmp_path: Path) -> None:
    rows = [
        _row(pipeline_id="pid-aaaaaaaaaaaa",
             failure_reason="lake_build_error",
             failure_detail="error: combine patch failed elaboration",
             strategy_proposal="### Decomposition\n4 sub-goals"),
    ]
    out = context_files.write_past_backward(rows, tmp_path)
    assert out is not None
    assert out.name == "PAST_VERIFY_FAILURES.md"
    text = out.read_text(encoding="utf-8")
    assert "combine patch failed elaboration" in text
    assert "Decomposition" in text


def test_write_past_backward_empty_returns_none(tmp_path: Path) -> None:
    """No verify-failure rows → no companion file. F55 progress notes
    do NOT contribute to this file (they live only in Context.md inline
    per F43-style 'must-see channel' lesson)."""
    assert context_files.write_past_backward([], tmp_path) is None


# ---------------------------------------------------------------------
# F30 — companion files run failure_detail through smart_truncate_stderr
# (the same pre-F26 noise — LEAN_PATH dumps, lake build trace — was
# bloating PAST_DIRECT_ATTEMPTS.md, paid only when the agent actually reads it
# but still wasted bytes when it does)
# ---------------------------------------------------------------------

def test_past_attempts_strips_lean_path_dump(tmp_path: Path) -> None:
    """F30 + F32: PAST_DIRECT_ATTEMPTS.md must surface the actual error
    line, and after F32 the LEAN_PATH dump is removed entirely (not
    just reordered)."""
    big_lean_path = "trace: .> LEAN_PATH=" + ";".join(
        f"D:/lake/packages/p{i}/lib/lean" for i in range(120))
    detail = (
        big_lean_path + "\n"
        + "/x.lean:7:2: error: Type mismatch on `ZMod.val_natCast`\n"
        + "error: Lean exited with code 1\n"
    )
    deads = [_row(pipeline_id="pid-aaaaaaaaaaaa",
                  failure_reason="lake_build_error",
                  failure_detail=detail, proposal_md="")]
    out = context_files.write_past_attempts(deads, tmp_path)
    text = out.read_text(encoding="utf-8")

    # The actual error line is preserved
    assert "Type mismatch" in text
    assert "ZMod.val_natCast" in text
    # F32: LEAN_PATH dump fully gone, plus the redundant exit-code line
    assert "LEAN_PATH=" not in text
    assert "Lean exited with code" not in text


def test_past_attempts_preserves_proposal_md(tmp_path: Path) -> None:
    """proposal_md is the agent's own prose — must NOT be truncated by
    smart_truncate (which is for lake stderr noise)."""
    long_proposal = (
        "# My strategy\n\n"
        + "This is a substantial decomposition rationale. " * 50
        + "\nKey insight: use the Lindenbaum lemma."
    )
    deads = [_row(pipeline_id="pid-bbbbbbbbbbbb",
                  failure_reason="lake_build_error",
                  failure_detail="error: trivial",
                  proposal_md=long_proposal)]
    out = context_files.write_past_attempts(deads, tmp_path)
    text = out.read_text(encoding="utf-8")
    # Full proposal_md is preserved verbatim
    assert "# My strategy" in text
    assert "Lindenbaum lemma" in text
    assert long_proposal in text


def test_past_attempts_short_failure_detail_unchanged(tmp_path: Path) -> None:
    """Below the smart_truncate budget threshold, failure_detail is
    passed through unchanged."""
    detail = "error: agent rc=124"
    deads = [_row(pipeline_id="pid-cccccccccccc",
                  failure_reason="agent_timeout",
                  failure_detail=detail, proposal_md="")]
    out = context_files.write_past_attempts(deads, tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "agent rc=124" in text


def test_past_backward_strips_lean_path_dump(tmp_path: Path) -> None:
    """Same F30+F32 treatment for PAST_VERIFY_FAILURES.md."""
    big_lean_path = "trace: .> LEAN_PATH=" + "x" * 3000
    detail = (
        big_lean_path + "\n"
        + "error: combine patch failed elaboration\n"
    )
    rows = [_row(pipeline_id="pid-vvvvvvvvvvvv",
                 failure_reason="lake_build_error",
                 failure_detail=detail,
                 strategy_proposal="### Decomp\n3 sub-goals")]
    out = context_files.write_past_backward(rows, tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "combine patch failed elaboration" in text
    assert "3 sub-goals" in text  # proposal preserved
    assert "LEAN_PATH=" not in text


# ---------------------------------------------------------------------
# F55 — partial-PROPOSAL injection through compile_context
# ---------------------------------------------------------------------

def test_compile_context_inlines_prior_progress_note_for_backward(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When `.drafts/backward_g<gid>.md` exists (postmortem note from
    a prior timed-out spawn), Backward Context.md surfaces it inline
    as 'Your previous progress note' so the agent picks up from the
    captured state + blocker sketch instead of starting fresh.

    The companion file `PAST_VERIFY_FAILURES.md` is intentionally NOT
    augmented with the note — F43 lesson says agents miss companion
    files, so the inline section is the canonical surface."""
    from Tooling.pipeline import _drafts
    gid = _seed_goal(conn)
    workspace = tmp_path
    attempts_dir = workspace / ".attempts" / "pid-current"
    attempts_dir.mkdir(parents=True)
    problem_dir = workspace / "Problems" / "p"
    problem_dir.mkdir(parents=True)
    # Simulate a prior timed-out spawn whose postmortem wrote _progress.md
    prior_attempts = workspace / ".attempts" / "pid-prior"
    prior_attempts.mkdir(parents=True)
    (prior_attempts / "_progress.md").write_text(
        "Kelly minimiser route, 4 sub-goals; blocked on naming the "
        "perpendicular-distance lemma.",
        encoding="utf-8",
    )
    _drafts.persist_partials(
        attempts_dir=prior_attempts, problem_dir=problem_dir,
        kind="backward", goal_id=gid,
    )
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal,
                          intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir, kind="backward")
    text = out.read_text(encoding="utf-8")
    assert "Your previous progress note" in text
    assert "Kelly minimiser" in text
    # Companion file does NOT carry the progress note (F55 design choice)
    if (attempts_dir / "PAST_VERIFY_FAILURES.md").exists():
        companion = (attempts_dir / "PAST_VERIFY_FAILURES.md").read_text(
            encoding="utf-8")
        assert "Kelly minimiser" not in companion


def test_compile_context_inlines_prior_progress_note_for_builder(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Same surface for Builder. The note is the postmortem dump after
    a Builder-spawn timeout."""
    from Tooling.pipeline import _drafts
    gid = _seed_goal(conn)
    workspace = tmp_path
    attempts_dir = workspace / ".attempts" / "pid-current"
    attempts_dir.mkdir(parents=True)
    problem_dir = workspace / "Problems" / "p"
    problem_dir.mkdir(parents=True)
    prior_attempts = workspace / ".attempts" / "pid-prior"
    prior_attempts.mkdir(parents=True)
    (prior_attempts / "_progress.md").write_text(
        "Tried `omega` then `polyrith`; need a divisibility lemma I can't name.",
        encoding="utf-8",
    )
    _drafts.persist_partials(
        attempts_dir=prior_attempts, problem_dir=problem_dir,
        kind="builder", goal_id=gid,
    )
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal,
                          intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir, kind="builder")
    text = out.read_text(encoding="utf-8")
    assert "Your previous progress note" in text
    assert "polyrith" in text


def test_compile_context_no_partial_section_when_no_draft(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """No `.drafts/<kind>_g<gid>.md` → no inline progress-note section
    (most spawns succeed first try; postmortem only fires on timeout)."""
    gid = _seed_goal(conn)
    workspace = tmp_path
    attempts_dir = workspace / ".attempts" / "pid-current"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal,
                          intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir, kind="backward")
    text = out.read_text(encoding="utf-8")
    assert "Your previous progress note" not in text


# ---------------------------------------------------------------------
# Integration: compile_context produces summary-form Context.md AND
# companion files, and Context.md stays small even with many attempts
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection) -> int:
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done) VALUES (?, ?, 1)",
        ("p", db.now()),
    )
    return db.insert_goal(
        conn, problem="p", slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root",
    )


def _record_pipeline(conn, pid):
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, "Builder", "1", "Goal", "failed", "failed",
         db.now(), db.now()),
    )
    conn.commit()


def test_compile_context_writes_companion_past_attempts(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """End-to-end: dead_attempts → Context.md inlines the full content
    (F43). Companion PAST_DIRECT_ATTEMPTS.md still written for forensics.

    F32: even the companion file no longer carries the LEAN_PATH
    dump — strip_lake_noise unconditionally drops infra lines
    (signal-free regardless of where they're rendered)."""
    gid = _seed_goal(conn)
    _record_pipeline(conn, "pid-q1")
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal", pipeline_id="pid-q1",
        failure_reason="lake_build_error",
        failure_detail=(
            "✖ [10/10] Building x (3s)\n"
            "trace: .> LEAN_PATH=D:\\fake\\path;...\n"
            "error: Type mismatch on `Foo.bar`\n"
        ),
    )
    attempts_dir = tmp_path / ".attempts" / "pid-q1"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")

    # F43: full content inlined into Context.md
    assert "Direct attempts on this goal" in text
    assert "Type mismatch on `Foo.bar`" in text
    assert "LEAN_PATH=" not in text  # F32 noise stripped here too

    # Companion file still written (forensics) — verbatim error preserved
    past = (attempts_dir / "PAST_DIRECT_ATTEMPTS.md").read_text(encoding="utf-8")
    assert "Foo.bar" in past
    assert "Type mismatch" in past
    # F32: companion file is also strip_lake_noise'd — no infra dump
    assert "LEAN_PATH=" not in past


def test_compile_context_size_with_many_attempts_under_smart_truncate(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Context.md carries a DIGEST per attempt; the companion file
    carries the autopsies. That split is what both surfaces have always
    claimed — `write_past_attempts` tells its reader "Context.md shows a
    1-line digest per attempt" — but one renderer served both audiences
    until 2026-08-11, so each attempt shipped twice (measured on the
    live tree, g7491: 10,527 B of goal history, 5 attempts).

    The invariant is the SPLIT, not a byte floor: every attempt is
    accounted for inline, its error is named, and the bulk lives in the
    file the section header points at."""
    gid = _seed_goal(conn)
    big_stderr_template = (
        "✖ [N/N] Building x\n"
        "trace: .> LEAN_PATH=" + "x" * 1500 + "\n"
        "error: Type mismatch line {n}\n"
    )
    for i in range(5):
        pid = f"pid-attempt-{i:02d}"
        _record_pipeline(conn, pid)
        db.record_dead_attempt(
            conn, target_id=gid, target_kind="Goal", pipeline_id=pid,
            failure_reason="lake_build_error",
            failure_detail=big_stderr_template.format(n=i),
            proposal_md="## Strategy " + "y" * 1000,
        )

    attempts_dir = tmp_path / ".attempts" / "pid-current"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal,
                          intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir)
    ctx_text = out.read_text(encoding="utf-8")
    past_text = (attempts_dir / "PAST_DIRECT_ATTEMPTS.md").read_text(
        encoding="utf-8")

    # Every attempt is accounted for inline, and named by what failed.
    assert ctx_text.count("### Attempt ") == 5
    for i in range(5):
        assert f"Type mismatch line {i}" in ctx_text
    # The bulk stays in the companion file the header points at, and the
    # inline surface is a fraction of it — the whole point of the split.
    assert len(past_text) > 3 * len(ctx_text)
    assert "LEAN_PATH=" not in ctx_text
    # The full proposal text is companion-only.
    assert "y" * 1000 in past_text
    assert "y" * 1000 not in ctx_text


def test_only_the_newest_attempts_note_rides_inline(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """The most recent note is the hand-off — it names the blocker the
    next spawn picks up from, so it rides in full. Older notes collapse
    to their own title line plus the pointer: keeping every note inline
    replayed the whole failure history verbatim on every spawn, forever
    (g7491 ran five attempts). The title is the writer's own first line,
    which `force_progress.md` asks for."""
    import json
    gid = _seed_goal(conn)
    for i in range(3):
        pid = f"pid-note-{i:02d}"
        _record_pipeline(conn, pid)
        db.record_dead_attempt(
            conn, target_id=gid, target_kind="Goal", pipeline_id=pid,
            failure_reason="agent_timeout",
            failure_detail=f"agent rc=124\nrc=124\ntimed out on step {i}",
            artifacts=json.dumps({"_progress.md":
                                  f"# blocked on step {i}\n\nbody {i} "
                                  + "z" * 400}))
    attempts_dir = tmp_path / ".attempts" / "pid-current"
    attempts_dir.mkdir(parents=True)
    out = compile_context(conn, goal=db.get_goal(conn, gid),
                          intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")

    newest = "z" * 400
    assert text.count(newest) == 1          # exactly one note body inline
    # …and every attempt is still named, by its title and its verdict.
    for i in range(3):
        assert f"blocked on step {i}" in text
        assert f"timed out on step {i}" in text
    assert "PAST_DIRECT_ATTEMPTS.md" in text
    # The framework's own rc preamble is never the digest — every
    # timeout would read identically if it were.
    assert "\nagent rc=124\n" not in text


def test_smart_truncate_does_not_print_the_same_detail_twice(
) -> None:
    """`force_reorder` appends a trace head for context. When the whole
    detail is already "important", that head IS the reordered text —
    the attempt blocks carried their timeout autopsy verbatim twice."""
    from Tooling.quality.diagnostics import smart_truncate_stderr
    detail = ("error: build failed on Foo.lean\n"
              "error: unknown identifier bar")
    out = smart_truncate_stderr(detail, budget=4000, force_reorder=True)
    assert out.count("unknown identifier bar") == 1
    assert "--- trace head ---" not in out


def test_compile_context_no_companion_when_no_history(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Fresh goal, no dead_attempts → no PAST_DIRECT_ATTEMPTS.md emitted."""
    gid = _seed_goal(conn)
    attempts_dir = tmp_path / ".attempts" / "pid-fresh"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    compile_context(conn, goal=goal,
                    intent=ProblemIntent(problem="p", charter="T"),
                    attempts_dir=attempts_dir)
    assert not (attempts_dir / "PAST_DIRECT_ATTEMPTS.md").exists()
    assert not (attempts_dir / "PAST_VERIFY_FAILURES.md").exists()


# ---------------------------------------------------------------------
# F43 — kind-aware section selection in compile_context
# ---------------------------------------------------------------------

def _seed_goal_with_history(conn: sqlite3.Connection,
                            tmp_path: Path) -> tuple[int, Path]:
    """Seed: 1 dead_attempt on the goal + 1 dead strategy with a
    Verify failure on it. Returns (goal_id, attempts_dir)."""
    gid = _seed_goal(conn)
    # Goal-level dead attempt (Builder-class history)
    _record_pipeline(conn, "pid-builder-fail")
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal",
        pipeline_id="pid-builder-fail",
        failure_reason="lake_build_error",
        failure_detail="error: BUILDER-LEVEL Lean error here",
        proposal_md="builder PROPOSAL contents",
    )
    # Strategy + Verify-level dead attempt (Backward-class history)
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid-strat",
        proposal_md="strategy decomposition prose",
    )
    conn.execute(
        "UPDATE strategies SET status='dead' WHERE id=?", (sid,))
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("pid-verify-fail", "Verify", str(sid), "Strategy",
         "failed", "failed", db.now(), db.now()))
    db.record_dead_attempt(
        conn, target_id=sid, target_kind="Strategy",
        pipeline_id="pid-verify-fail",
        failure_reason="lake_build_error",
        failure_detail="error: VERIFY-LEVEL combine elaboration failed",
    )
    conn.commit()
    attempts_dir = tmp_path / ".attempts" / "pid-current"
    attempts_dir.mkdir(parents=True)
    return gid, attempts_dir


def test_compile_context_builder_kind_includes_attempts_excludes_verifies(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F43 — Builder gets the direct_attempts sub-section only.
    Sibling-decompositions sub-section is
    irrelevant to Builder (different layer of failure) and would be
    pure attention noise."""
    gid, attempts_dir = _seed_goal_with_history(conn, tmp_path)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal,
                          intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir, kind="builder")
    text = out.read_text(encoding="utf-8")
    assert "Direct attempts on this goal" in text
    assert "BUILDER-LEVEL Lean error" in text
    assert "Sibling decompositions that failed Verify" not in text
    assert "VERIFY-LEVEL" not in text


def test_compile_context_backward_kind_sees_both_attempts_and_verifies(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """C3 — `### Direct attempts on this goal` is now kind-agnostic
    (a goal's failure history is its own property, not the pipeline's).
    Backward retry needs this to see SG-g142-class cases (its own
    prior `lake_build_error` rows) AND inherited Builder declines.
    `### Sibling decompositions that failed Verify` stays Backward-
    gated (no actionable read for Builder)."""
    gid, attempts_dir = _seed_goal_with_history(conn, tmp_path)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal,
                          intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir, kind="backward")
    text = out.read_text(encoding="utf-8")
    assert "Sibling decompositions that failed Verify" in text
    assert "VERIFY-LEVEL" in text
    # C3: Backward also sees direct_attempts (was the F43 gate)
    assert "Direct attempts on this goal" in text
    assert "BUILDER-LEVEL" in text


def test_compile_context_no_kind_renders_both_sections(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Back-compat: callers (typically tests) that don't pass `kind`
    get both sections — preserves the pre-F43 behavior so existing
    test fixtures keep working unchanged."""
    gid, attempts_dir = _seed_goal_with_history(conn, tmp_path)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal,
                          intent=ProblemIntent(problem="p", charter="T"),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")
    assert "BUILDER-LEVEL" in text
    assert "VERIFY-LEVEL" in text


def test_compile_context_companion_files_always_written(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F43: companion files are forensics + future-proof storage; they
    must keep being written regardless of which inline section the
    current pipeline kind is rendering. A Backward with direct-attempts
    history off the inline path still has PAST_DIRECT_ATTEMPTS.md on disk."""
    gid, attempts_dir = _seed_goal_with_history(conn, tmp_path)
    goal = db.get_goal(conn, gid)
    compile_context(conn, goal=goal,
                    intent=ProblemIntent(problem="p", charter="T"),
                    attempts_dir=attempts_dir, kind="backward")
    # Backward inline path skipped the direct_attempts sub-section in Context.md,
    # but the companion file must still exist (forensics + agent can
    # still Read on demand if it ever wants to).
    assert (attempts_dir / "PAST_DIRECT_ATTEMPTS.md").exists()
    assert (attempts_dir / "PAST_VERIFY_FAILURES.md").exists()


# ---------------------------------------------------------------------
# The timeout hint (#186, 2026-08-11)
# ---------------------------------------------------------------------

def _attempt(reason: str, pid: str = "abcdef123456") -> dict:
    return {"pipeline_id": pid, "failure_reason": reason,
            "failure_detail": "", "artifacts": None}


def _history(*reasons: str) -> str:
    return "\n".join(_section_goal_history(
        direct_events=[_attempt(r) for r in reasons],
        verify_events=[], dead_strat_events=[], infeasible_sub_events=[],
        show_verifies=False))


def test_a_timed_out_goal_is_told_what_running_out_of_clock_means():
    """A timeout is a legitimate attempt — full budget, nothing
    delivered — but nothing told the next worker what it MEANS. g7491
    timed out three times across three days and three strategies, each
    spawn re-attacking the same size; the first goal to meet the raised
    1800s ceiling timed out against that too. The way out (outsource the
    heavy self-contained part) is the whole point of the message: a bare
    fact would be one more wall."""
    text = _history("agent_timeout", "lake_build_error", "agent_timeout")
    assert "2 earlier attempt(s) ran out of wall clock" in text
    assert "`new_<slug>.lean` sub-goal" in text


def test_the_timeout_hint_stays_away_when_nothing_timed_out():
    text = _history("lake_build_error", "agent_declined")
    assert "ran out of wall clock" not in text


def test_a_watchdog_kill_is_not_counted_as_a_timeout():
    """User call, 2026-08-11: `agent_stuck_thinking` is the model wedged
    on a silent stream, not a burden that did not fit in the budget.
    Folding it in would aim the decomposition advice at the wrong
    failure."""
    text = _history("agent_stuck_thinking", "agent_stuck_thinking")
    assert "ran out of wall clock" not in text


def test_the_hint_carries_the_count_the_worker_cannot_see():
    """One timeout may be luck; three across three strategies is a size
    problem — and a spawn only ever knows its own turn."""
    assert "1 earlier attempt(s)" in _history("agent_timeout")
    assert "3 earlier attempt(s)" in _history(
        "agent_timeout", "agent_timeout", "agent_timeout")
