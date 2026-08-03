"""Prompt-template extraction pins (task #10(c)).

The rescue / force-progress / feedback prompt text moved from inline
Python strings to Tooling/prompts/ templates. These snapshots pin the
RENDERED output to the historical wording — an accidental template edit
that would change what agents see trips here (the SG-run-#10 drift class
these templates were extracted to prevent).
"""
from __future__ import annotations

from pathlib import Path

from Tooling.pipeline._feedback import SURVIVOR_PROMPT_SECTION
from Tooling.pipeline._retry import _build_fresh_rescue_stage2_prompt


def test_fresh_rescue_stage2_renders_historical_text(tmp_path):
    ad = tmp_path / ".attempts" / "p1"
    out = _build_fresh_rescue_stage2_prompt(ad, True, 3)
    assert out.startswith(
        "The previous session was killed mid-think after exceeding the "
        "wall-clock budget. The previous session's full conversation log "
        f"is at `{ad}/_broken_session.jsonl`.")
    # the SG-run-#10 fix: the explicit output-location line must survive
    assert (f"All output files must be written into `{ad}/` — use "
            "absolute paths in your Write calls." in out)
    for opt in ("(a) `", "(b) `", "(c) `", "(d) bail"):
        assert opt in out
    assert out.endswith("Act now. 3 minutes left.")
    assert "__" not in out          # no unsubstituted placeholder


def test_fresh_rescue_stage2_unrecoverable_log_branch(tmp_path):
    ad = tmp_path / "a"
    out = _build_fresh_rescue_stage2_prompt(ad, False, 5)
    assert ("The previous session's log was not recoverable. Work "
            f"from `{ad}/Context.md` alone.") in out
    assert out.endswith("Act now. 5 minutes left.")


def test_force_progress_template_renders(tmp_path):
    from Tooling.pipeline import _retry
    out = _retry._render_prompt(
        "_shared/force_progress.md",
        LOG_NOTE="NOTE.", ATTEMPTS_DIR=str(tmp_path))
    assert out.startswith(
        "You are a fresh session brought in only to write a checkpoint "
        "note. NOTE.")
    assert f"Do NOT modify `{tmp_path}/patch.lean`." in out
    assert out.endswith(
        "make it concrete, name the Mathlib lemmas or sub-shapes you'd "
        "try next.")
    assert "__" not in out


def test_feedback_survivor_keeps_format_contract():
    assert SURVIVOR_PROMPT_SECTION.startswith(
        "## Framework feedback — for the framework developer")
    assert "{feedback_path}" in SURVIVOR_PROMPT_SECTION
    assert SURVIVOR_PROMPT_SECTION.endswith("or exactly `(none)`.")
    assert "__FEEDBACK_PATH__" not in SURVIVOR_PROMPT_SECTION


def test_templates_exist_in_prompts_dir():
    from Tooling.pipeline import PROMPT_DIR
    for name in ("fresh_rescue_stage2.md", "fresh_rescue_stage2_mint.md",
                 "force_progress.md", "feedback_survivor.md"):
        assert (Path(PROMPT_DIR) / "_shared" / name).is_file(), name


def test_mint_rescue_ships_what_the_mint_parse_reads(tmp_path):
    """Feedback 107: the goal-shaped rescue menu told mint takeovers to
    write `patch.lean`, but Forward's parse reads `new_forward.lean`
    only — every mint rescue was structurally unable to succeed. The
    mint template must name the consumed artifact and never the
    goal-job ones."""
    ad = tmp_path / ".attempts" / "p1"
    out = _build_fresh_rescue_stage2_prompt(
        ad, True, 3, template="_shared/fresh_rescue_stage2_mint.md")
    assert "new_forward.lean" in out
    assert "patch.lean` +" not in out
    assert f"{ad}/new_forward.lean" in out.replace("\\", "/") or \
        "new_forward.lean" in out
    assert "MINT job" in out
    assert "_progress.md" in out          # bail stays available


def test_forward_passes_the_mint_rescue_template():
    """The call-site pin: forward's run_lsp_edit_loop must select the
    mint menu — losing the kwarg silently reverts to the goal menu."""
    src = (Path(__file__).resolve().parents[1] / "Tooling" / "pipeline"
           / "forward.py").read_text(encoding="utf-8")
    assert 'rescue_template="_shared/fresh_rescue_stage2_mint.md"' in src
