"""The agent-facing payload is TERSE by default (2026-09-07).

Measured that morning over 574 real `apply_edit` responses: 9.9 KB
average, 62.7 KB worst, and one `errors_at` reached its worker as
`truncated output (original token count: 18055)`. Four agents filed the
same complaint independently (10:00, 10:21, 10:52, 11:16) — "large
post-edit goal dumps were repeatedly truncated and obscured the first
real failure". Truncation drops the TAIL, which is where the second
error lives.

These tests pin the contract: errors first and bounded, warnings folded
to one line per linter category, the bearing fields (anchor failure,
`scope_balance`, `elaborating`) never trimmed, and `verbose=true`
returning everything.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from Tooling.lsp import gateway as lsp_gateway
from Tooling.lsp.gateway import terse


# ─── fixtures: fake diagnostics, no Lean ──────────────────────

#: One `unusedSimpArgs` warning as Lean actually prints it: the argument
#: name differs on every one of them, and the disable-note at the foot
#: is the linter naming itself.
def _simp_warning(line: int, arg: str) -> dict:
    return {
        "range": {"start": {"line": line - 1, "character": 4}},
        "severity": 2,
        "message": (f"This simp argument is unused:\n  {arg}\n\nHint: Omit "
                    f"it from the simp argument list.\n  simp [{arg}]\n\n"
                    f"Note: This linter can be disabled with `set_option "
                    f"linter.unusedSimpArgs false`"),
    }


def _unsolved_goals(line: int, case: str, n_hyp: int = 40) -> dict:
    hyps = "\n".join(f"h{i}{case} : Disjoint A{i} B{i}" for i in range(n_hyp))
    return {
        "range": {"start": {"line": line - 1, "character": 2}},
        "severity": 1,
        "message": f"unsolved goals\ncase {case}\n{hyps}\n⊢ GOAL_{case}",
    }


def _fixture_diags(n_warn: int = 60, n_err: int = 8) -> list:
    out = [_simp_warning(10 + i, f"hA{i}") for i in range(n_warn)]
    out += [_unsolved_goals(100 + i, f"c{i}") for i in range(n_err)]
    return out


class _GoalBackend:
    """`_DiagBackend` plus a plainGoal that answers — the terse payload
    keeps the goal at the edit's END, so a backend that cannot produce
    one would test the error path instead of the contract."""

    def __init__(self, diags):
        self._diags = diags

    def clear_diagnostics(self, *a, **kw): pass
    def did_change_full(self, *a, **kw): pass
    def wait_for_diagnostics(self, *a, **kw): pass
    def diagnostics_for(self, *a, **kw): return list(self._diags)
    def plain_goal(self, *a, **kw): return {"rendered": "⊢ CURSOR"}


def _run_apply(monkeypatch, tmp_path, diags, edits, **kw) -> dict:
    from tests.test_lsp_gateway import _setup_validate_session
    content = "line one\nline two\nend Problems.p\n"
    (tmp_path / "x.lean").write_text(content, encoding="utf-8")
    ctx = _setup_validate_session(monkeypatch, tmp_path, _GoalBackend(diags))
    lsp_gateway._state.sessions["tok-A"].file_content = content
    try:
        return json.loads(asyncio.run(lsp_gateway.apply_edit(edits, **kw)))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)


def _run_errors_at(monkeypatch, tmp_path, diags, **kw) -> dict:
    from tests.test_lsp_gateway import _setup_validate_session
    content = "line one\nline two\nend Problems.p\n"
    (tmp_path / "x.lean").write_text(content, encoding="utf-8")
    ctx = _setup_validate_session(monkeypatch, tmp_path, _GoalBackend(diags))
    lsp_gateway._state.sessions["tok-A"].file_content = content
    try:
        return json.loads(asyncio.run(lsp_gateway.errors_at(**kw)))
    finally:
        lsp_gateway._session_ctx.reset(ctx)
        lsp_gateway._state.sessions.pop("tok-A", None)


# ─── the payload ───────────────────────────────────────────────

def test_terse_apply_edit_fits_in_a_turn_and_names_the_first_goal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """60 warnings + 8 forty-hypothesis errors — today's payload for
    that is ~40 KB and gets truncated before the agent reaches the
    errors. Terse: under 3 KB, first error's goal intact."""
    out = _run_apply(monkeypatch, tmp_path, _fixture_diags(),
                     [{"replace": "line one", "with": "a\nb\nc"}])
    blob = json.dumps(out, ensure_ascii=False)
    assert len(blob) < 3072, f"terse payload is {len(blob)} bytes"
    # The first error keeps its whole state — that is where it works next.
    first = out["diagnostics"][0]
    assert "⊢ GOAL_c0" in first["message"]
    assert "h0c0 : Disjoint A0 B0" in first["message"]
    assert "hypotheses_hidden" not in first
    # Every other error keeps its goal and COUNTS what it dropped.
    rest = out["diagnostics"][1]
    assert "⊢ GOAL_c1" in rest["message"]
    assert "h0c1" not in rest["message"]
    assert rest["hypotheses_hidden"] == 40
    assert out["error_count"] == 8
    # The "ask for verbose" sentence is said once, not once per error.
    assert blob.count("verbose=true") == 1
    assert "hypotheses_hidden" in out["terse_note"]


def test_terse_folds_sixty_distinct_warnings_into_one_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The byte-identical fold left all 60 in the payload: each names a
    different simp argument. The linter's own disable-note is the key."""
    out = _run_apply(monkeypatch, tmp_path, _fixture_diags(),
                     [{"replace": "line one", "with": "a\nb\nc"}])
    assert out["warnings"] == [
        "linter.unusedSimpArgs ×60 — line(s) 10, 11, 12, 13, 14, 15"
        " (+54 more)"]
    assert "verbose" in out["terse_note"]
    # Warnings are not errors and must not be counted as any.
    assert not any(w["severity"] != "error" for w in out["diagnostics"])


def test_terse_caps_the_error_list_and_says_how_many_are_left(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    out = _run_apply(monkeypatch, tmp_path, _fixture_diags(0, 12),
                     [{"replace": "line one", "with": "a\nb\nc"}])
    assert len(out["diagnostics"]) == terse.MAX_ERRORS
    assert out["error_count"] == 12
    assert "4 more errors" in out["more_errors"]
    assert "verbose=true" in out["more_errors"]
    assert "warnings" not in out


def test_verbose_returns_the_whole_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`verbose=true` is the escape hatch that makes the trim safe: no
    information is destroyed, only deferred."""
    out = _run_apply(monkeypatch, tmp_path, _fixture_diags(),
                     [{"replace": "line one", "with": "a\nb\nc"}],
                     verbose=True)
    blob = json.dumps(out, ensure_ascii=False)
    assert len(blob) > 20000
    assert "warnings" not in out and "more_errors" not in out
    # Every warning and every error, with every hypothesis: the escape
    # hatch has to return the payload the trim was applied to.
    assert len(out["diagnostics"]) == 68
    assert blob.count("This simp argument is unused") == 60
    assert "h39c7 : Disjoint A39 B39" in blob
    # The fields the terse payload drops.
    assert out["replaced_text"] == "line one"
    assert out["goal_at_edit_start"] == "⊢ CURSOR"


def test_terse_drops_the_start_goal_but_never_the_only_goal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """2026-08-06 (feedback x6, both arms): after a multi-line
    replacement the agent wants the state at the END of what it wrote,
    and paid a second `goal_at` round-trip when only the top came back.
    The terse payload keeps the one the comment defends. A single-line
    edit queries both ends at the same position, so its one goal still
    rides under the START name rather than vanishing."""
    multi = _run_apply(monkeypatch, tmp_path, [],
                       [{"replace": "line one", "with": "a\nb\nc"}])
    single = _run_apply(monkeypatch, tmp_path, [],
                        [{"replace": "line one", "with": "a"}])
    assert "goal_at_edit_start" not in multi
    assert multi["goal_at_edit_end"] == "⊢ CURSOR"
    assert multi["goal_at_edit_end_note"] == lsp_gateway._GOAL_AT_EDIT_END_NOTE
    assert "goal_at_edit_end" not in single
    assert single["goal_at_edit_start"] == "⊢ CURSOR"


def test_the_bearing_fields_are_never_trimmed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`scope_balance` and the anchor-failure report are how an agent
    knows WHERE it is; a payload that trims them saves bytes by
    removing the reason to send it."""
    out = _run_apply(monkeypatch, tmp_path, _fixture_diags(),
                     [{"replace": "line one", "with": "a\nb\nc"}])
    assert out["scope_balance"] == -1
    assert "more `end`" in out["scope_warning"]
    assert "end of file" in out["post_edit_region"]
    rejected = _run_apply(monkeypatch, tmp_path, _fixture_diags(),
                          [{"replace": "no such anchor", "with": "x"}])
    assert "rejected" in rejected["edit"] and "file unchanged" in \
        rejected["edit"]
    assert rejected["edit_index"] == 1
    assert "does not appear in the file" in rejected["error"]


def test_a_long_edited_region_is_elided_in_the_middle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The echo exists so the agent re-anchors from ground truth, not so
    it can read back the 60 lines it just wrote."""
    body = "\n".join(f"x{i}" for i in range(60))
    out = _run_apply(monkeypatch, tmp_path, [],
                     [{"replace": "line one", "with": body}])
    region = out["post_edit_region"]
    assert "x0" in region and "x59" in region
    assert "x30" not in region
    assert "more lines of the edited region" in region
    full = _run_apply(monkeypatch, tmp_path, [],
                      [{"replace": "line one", "with": body}], verbose=True)
    assert "x30" in full["post_edit_region"]


# ─── errors_at ─────────────────────────────────────────────────

def test_errors_at_is_terse_but_a_line_query_is_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A `line` query is the agent asking a precise question and it
    already bounds the answer — it comes back whole, warnings and all."""
    diags = _fixture_diags()
    terse_out = _run_errors_at(monkeypatch, tmp_path, diags)
    assert len(json.dumps(terse_out, ensure_ascii=False)) < 3072
    assert terse_out["error_count"] == 8
    assert terse_out["count"] == 68     # raw total, unchanged
    assert len(terse_out["warnings"]) == 1

    exact = _run_errors_at(monkeypatch, tmp_path, diags, line=10)
    assert len(exact["diagnostics"]) == 1
    assert "Hint: Omit it" in exact["diagnostics"][0]["message"]

    verbose = _run_errors_at(monkeypatch, tmp_path, diags, verbose=True)
    assert len(verbose["diagnostics"]) == 68
    assert "warnings" not in verbose


# ─── the helpers, directly ─────────────────────────────────────

def test_collapse_folds_warnings_by_category_and_errors_verbatim():
    """Errors fold only on the identical message: two errors sharing a
    first line are two problems, and merging them would hide one."""
    def diags():
        # A FACTORY, not a list: `_collapse_repeats` folds by mutating
        # the survivor in place, so a second call on the same objects
        # would score the first call's result.
        return [
            {"line": 3, "col": 0, "severity": "warning",
             "message": "This simp argument is unused:\n  hA\n\nNote: This "
                        "linter can be disabled with `set_option "
                        "linter.unusedSimpArgs false`"},
            {"line": 9, "col": 0, "severity": "warning",
             "message": "This simp argument is unused:\n  hB\n\nNote: This "
                        "linter can be disabled with `set_option "
                        "linter.unusedSimpArgs false`"},
            {"line": 5, "col": 0, "severity": "error",
             "message": "unknown id x"},
            {"line": 6, "col": 0, "severity": "error",
             "message": "unknown id y"},
        ]
    out = terse._collapse_repeats(diags())
    assert len(out) == 3
    assert out[0]["category"] == "linter.unusedSimpArgs"
    assert out[0]["repeats"] == 2 and out[0]["also_lines"] == [9]
    assert "×2" in out[0]["message"]
    assert out[1]["message"] == "unknown id x" and "repeats" not in out[1]
    assert out[2]["message"] == "unknown id y"
    # `by_category=False` is what verbose asks for: today's fold exactly,
    # identical messages only and no rewrite of the survivor.
    plain = terse._collapse_repeats(diags(), by_category=False)
    assert len(plain) == 4
    assert all("category" not in p for p in plain)
    assert plain[0]["message"].startswith("This simp argument is unused")


def test_a_warning_with_no_linter_option_keys_on_its_first_line():
    diags = [{"line": n, "col": 0, "severity": "warning",
              "message": "declaration uses `sorry`"} for n in (4, 8)]
    out = terse._collapse_repeats(diags)
    assert len(out) == 1
    assert out[0]["category"] == "declaration uses `sorry`"
    assert terse._warning_line(out[0]) == (
        "declaration uses `sorry` ×2 — line(s) 4, 8")


def test_trim_leaves_a_message_that_carries_no_goal_alone():
    """A type mismatch is 400 chars and every line of it is the
    diagnosis — there is no hypothesis dump to drop."""
    msg = ("Type mismatch\n  finish hA\nhas type\n  P\nof sort `Prop` but is "
           "expected to have type\n  Q\nof sort `Type`")
    assert terse._trim_error(msg, keep_hypotheses=False) == (msg, 0)


def test_trim_keeps_prose_and_wrapped_goal_lines():
    """The lines a tactic prints before the state (its pattern, a
    `Note:`) are the diagnosis, not context — only `name : type` binders
    are hypotheses, and a goal that wraps keeps its continuation."""
    msg = ("Tactic `rewrite` failed: Did not find an occurrence of the "
           "pattern\n  f x\nh : A\nhlong : B\n"
           "⊢ first line of the goal\n    wrapped continuation")
    trimmed, hidden = terse._trim_error(msg, keep_hypotheses=False)
    assert hidden == 2
    assert "  f x" in trimmed
    assert "h : A" not in trimmed
    assert "⊢ first line of the goal\n    wrapped continuation" in trimmed


def test_a_runaway_message_is_capped_even_for_the_first_error():
    """The hypothesis trim does not bound a six-`case` `unsolved goals`
    (the worst real one was 13.6 KB, each case with its own goal)."""
    msg = "unsolved goals\n" + "⊢ " + ("g" * 9000)
    trimmed, _ = terse._trim_error(msg, keep_hypotheses=True)
    assert len(trimmed) < terse.ERR_MSG_MAX_CHARS + 200
    assert "more chars" in trimmed
