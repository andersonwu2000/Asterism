"""Unit tests for `Tooling/pipeline/_reflection.py` pure helpers.

The agent-spawning side of reflection is best-effort (any exception is
swallowed; the dispatcher must never block on a failed reflection)
and is exercised end-to-end by the PN run rather than mocked here.
This file pins the deterministic helpers: lesson-line counting,
prompt template substitution, before/after delta classification.
"""
from __future__ import annotations

from Tooling.pipeline._reflection import (
    _classify_delta,
    _count_lesson_lines,
    _render_prompt,
)


def test_count_lesson_lines_only_counts_bullets() -> None:
    content = (
        "## Lessons learned on this problem\n"
        "_Cross-spawn observations recorded by past agents..._\n"
        "\n"
        "- first lesson sentence\n"
        "- second lesson sentence\n"
    )
    assert _count_lesson_lines(content) == 2


def test_count_lesson_lines_handles_empty() -> None:
    assert _count_lesson_lines("") == 0
    assert _count_lesson_lines("\n\n") == 0
    # A header-only file (no bullets) is empty for cap purposes.
    assert _count_lesson_lines("## Lessons\n_blurb_\n") == 0


def test_count_lesson_lines_indented_bullet() -> None:
    # Allow some leading whitespace before the bullet (operator may
    # hand-edit with indentation).
    assert _count_lesson_lines("  - foo\n- bar\n") == 2


def test_render_prompt_substitutes_braced_fields() -> None:
    template = "Hello {name}, you are {role}."
    out = _render_prompt(template, name="alice", role="agent")
    assert out == "Hello alice, you are agent."


def test_render_prompt_does_not_format_lessons_content_with_braces() -> None:
    """LESSONS content can contain literal `{` (e.g. set-builder
    notation, Lean tactic blocks). Plain str.replace dodges
    str.format's brace-as-spec behavior."""
    template = "Existing: {lessons_content}"
    lessons = "- ‖a‖ ≤ ‖b‖ goal: try real_inner_le_norm\n- {x : ℕ // x > 0} doesn't reduce"
    out = _render_prompt(template, lessons_content=lessons)
    assert "{x : ℕ // x > 0}" in out


def test_classify_delta_skip_when_unchanged() -> None:
    same = "- existing lesson\n"
    assert _classify_delta(same, same) == "skip"


def test_classify_delta_wrote_when_appended() -> None:
    before = "- a\n"
    after = "- a\n- b\n"
    delta = _classify_delta(before, after)
    assert "wrote" in delta and "+1 line" in delta


def test_classify_delta_replaced_when_count_unchanged_but_content_differs() -> None:
    before = "- a\n- b\n- c\n"
    after = "- a\n- b\n- c-updated\n"
    delta = _classify_delta(before, after)
    assert "replaced" in delta


def test_classify_delta_unexpected_when_shrank() -> None:
    before = "- a\n- b\n"
    after = "- a\n"
    delta = _classify_delta(before, after)
    assert "unexpected" in delta
