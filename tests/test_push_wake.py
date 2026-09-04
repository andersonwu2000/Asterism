"""`Tooling.experiments.push_wake` — one two-turn Strategist push in a
rewound scratch workspace (the 2026-09-03 push experiment, arm B).

The runner writes: it mints a pipeline row, compiles a Context into
`.attempts/`, and spawns the seat against the workspace it is handed.
Pointed at the live workspace it would do all of that inside a running
daemon's state, so the guard is the first thing it does — before the
chdir that would make every workspace look like the current one.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

import pytest

from Tooling import experiments
from Tooling.experiments import push_wake


def test_push_wake_refuses_a_workspace_a_daemon_owns(tmp_path):
    """A `daemon.pid` beside the DB means the workspace is somebody
    else's; the push must refuse it rather than write into a live run."""
    ws = tmp_path / "live"
    (ws / ".asterism").mkdir(parents=True)
    (ws / "asterism.db").write_text("", encoding="utf-8")
    (ws / ".asterism" / "daemon.pid").write_text("4242 0.0", encoding="utf-8")
    with pytest.raises(SystemExit, match="scratch"):
        push_wake.assert_scratch(ws)


def test_push_wake_accepts_a_scratch_workspace(tmp_path):
    """The negative half: a workspace with no daemon marker passes, so
    the guard above is about the marker and not about refusing always."""
    ws = tmp_path / "scratch"
    (ws / ".asterism").mkdir(parents=True)
    (ws / "asterism.db").write_text("", encoding="utf-8")
    push_wake.assert_scratch(ws)


def test_a_runner_hardens_the_console_before_it_enters_the_pipeline(monkeypatch):
    """These runners are entry points into the same pipeline the CLI
    enters, and the CLI hardens the console first (`_force_utf8_io`).
    They did not: on a cp950 console the `⚠` in a length warning raised
    UnicodeEncodeError INSIDE the wake, and arm C run 2 of the push
    experiment (2026-09-03) died with its proposal written, its
    Adversary round spent and nothing committed."""
    monkeypatch.setattr(
        sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp950"))
    experiments.harden_console()
    print("⚠ i ∉ A")          # the two characters that killed the run
    sys.stdout.flush()
    assert "⚠ i ∉ A" in sys.stdout.buffer.getvalue().decode("utf-8")


# ---------------------------------------------------------------------
# theory_wake — the 2026-09-04 theory-wake experiment (arm 3)
# ---------------------------------------------------------------------

def test_theory_verdict_parser_takes_the_three_criteria_rubric():
    """`theory_judge.md` adjudicates 1..3 (Value / Relation / Rigour),
    not the batch judge's 1..5 — and `adversary.parse_verdict` refuses
    exactly that file, so the theory wake needs its own reader. Bending
    the shared parser instead would move the batch judge's contract."""
    from Tooling.experiments import theory_wake
    from Tooling.pipeline import adversary

    text = json.dumps({"criteria": {
        "1": ["clear: the persistent-coordinate statement is on no record"],
        "2": ["clear: it implies main in three lines; the wall is the "
              "chain step, attacked in Lemma 2"],
        "3": ["clear: reran the n<=5 census, 1,171,932 families"]},
        "reservations": ["the 6-point evidence is random, not exhaustive"]})
    v, err = theory_wake.parse_theory_verdict(text)
    assert err == ""
    assert v["verdict"] == "pass"
    assert v["criticisms"] == []
    assert v["reservations"] == [
        "the 6-point evidence is random, not exhaustive"]
    # The control: the batch parser rejects the very same bytes.
    assert adversary.parse_verdict(text)[0] is None


def test_theory_verdict_parser_refuses_a_missing_criterion():
    from Tooling.experiments import theory_wake
    text = json.dumps({"criteria": {"1": ["clear: new"],
                                    "2": ["clear: implies main"]}})
    v, err = theory_wake.parse_theory_verdict(text)
    assert v is None
    assert "3" in err


def test_theory_verdict_carries_the_fired_bullets_verbatim():
    """The fired bullets are what goes back to the author, so the
    objection text must survive the parse unedited — only the criterion
    label is added."""
    from Tooling.experiments import theory_wake
    objection = ("fired: Theorem 2's proof assumes |F_x| >= |F|/2, which "
                 "is the conjecture itself — close it or label it a "
                 "conjecture")
    text = json.dumps({"criteria": {
        "1": ["clear: not in the owner's notes"],
        "2": ["clear: implies main; the wall is Lemma 3"],
        "3": [objection, "fired: the n=6 census could not be reproduced"]}})
    v, err = theory_wake.parse_theory_verdict(text)
    assert err == ""
    assert v["verdict"] == "rebut"
    assert v["criticisms"] == [
        "[criterion 3] " + objection[len("fired: "):],
        "[criterion 3] the n=6 census could not be reproduced"]


def test_theory_verdict_parser_refuses_a_bare_clear():
    from Tooling.experiments import theory_wake
    text = json.dumps({"criteria": {"1": ["clear"],
                                    "2": ["clear: implies main"],
                                    "3": ["clear: reran the census"]}})
    v, err = theory_wake.parse_theory_verdict(text)
    assert v is None
    assert "bare" in err


def test_hide_owner_notes_empties_the_context_section(tmp_path):
    """`--hide-owner-notes` is the arm-3h variable: the Context must
    carry no `## Owner's notes` at all. The section is a module-level
    function the compiler calls by attribute, so the flag replaces it —
    and the control half asserts the notes ARE there without the flag,
    or the arm would be measuring nothing."""
    from Tooling.agent import context as _ctx
    from Tooling.experiments import theory_wake
    from Tooling.state import intent as _intent
    from Tooling.state import project_docs as pd

    pd.write(tmp_path, "Combinatorics", "user/split_note.md",
             "# SPLIT: abundance across a cut\n\nbody\n")
    who = _intent.ProblemIntent(problem="Combinatorics.union_closed")
    control = _ctx._section_owner_notes(who, tmp_path)
    assert control and control[0] == "## Notes on this problem"

    original = theory_wake.hide_owner_notes()
    try:
        assert _ctx._section_owner_notes(who, tmp_path) == []
        assert "## Notes on this problem" not in "\n".join(
            _ctx._section_owner_notes(who, tmp_path))
    finally:
        _ctx._section_owner_notes = original
    assert _ctx._section_owner_notes(who, tmp_path) == control


def test_theory_verdict_parser_takes_the_per_bullet_object_rendering():
    """The shape arm3h_r2's judge actually wrote (2026-09-04, run
    `arm3h_r2`, rollout `01a068eb`): `validate_json` mis-routes a
    three-criterion verdict into the AUDITOR's schema check
    (`mcp_tools.validate_json`: `"3"` is a list and `"5"` absent ⇒
    audit-shaped), so the judge — told by the prompt to validate before
    finishing — obeyed the tool and re-rendered its bullets as
    `{"goal_id", "verdict", "reason"}` objects. Both tries died on
    "criterion 3 must be a list of strings" and the whole wake was lost
    over a rendering of the SAME ruling. One bullet per objection is
    the contract; an object carrying the ruling and its prose satisfies
    it, exactly as the batch parser tolerates the legacy bare string."""
    from Tooling.experiments import theory_wake

    objection = ("The rank-three conjecture at report.md:206-207 is "
                 "stated under hypotheses that omit |H| < |G|, but the "
                 "falsifier discards every pair with |H| >= |G|.")
    text = json.dumps({"criteria": {
        "1": ["clear: Theorem 5's rank-three conclusions are on no record"],
        "2": ["clear: it reduces the MAIN claim; the wall is Lemma 3"],
        "3": [{"goal_id": 10670, "verdict": "fired", "reason": objection}],
        "4": [{"goal_id": 10670, "verdict": "clear",
               "reason": "no fourth criterion exists in this rubric"}]},
        "reservations": ["the arbitrary-rank wall remains open"]})
    v, err = theory_wake.parse_theory_verdict(text)
    assert err == ""
    assert v["verdict"] == "rebut"
    # verbatim, only the criterion label added — and criterion "4",
    # which this rubric does not have, is not smuggled in as a ruling.
    assert v["criticisms"] == [f"[criterion 3] {objection}"]


def test_theory_verdict_object_rendering_still_refuses_a_bare_clear():
    """The tolerance must not become a hole: an object whose ruling is
    `clear` and whose prose is empty is the bare clear the prompt
    forbids, and it must be refused in this rendering too."""
    from Tooling.experiments import theory_wake

    text = json.dumps({"criteria": {
        "1": ["clear: the statement is on no record"],
        "2": ["clear: it implies main; the wall is Lemma 3"],
        "3": [{"goal_id": 10670, "verdict": "clear"}]}})
    v, err = theory_wake.parse_theory_verdict(text)
    assert v is None
    assert "bare" in err


def test_theory_verdict_takes_several_clear_bullets_per_criterion():
    """One bullet per ITEM ruled on, clears included.

    "clear takes exactly one entry" was inherited from the batch judge,
    whose criteria rule on one proposal. A theory document carries
    several theorems and several leads, so a criterion that asks about
    them ("is every lead justified?") is answered one bullet per lead —
    and both arm5F runs ended `judge_no_verdict` on a verdict that was
    all-clear (`docs/internal/experiments/theory_wake/runs/arm5F_r1/
    verdict_r3_raw2.json` criterion 4, `…/arm5F_r2/verdict_r2_raw2.json`
    criterion 2). A criterion is clear iff EVERY bullet is a clear."""
    from Tooling.experiments import theory_wake

    keys = ("1", "2", "3", "4")
    text = json.dumps({"criteria": {
        "1": ["clear: Theorem 5 is a new bounded case of the obligation"],
        "2": ["clear: Lemmas 1-3 and the (g,h) split supply the work",
              "clear: I re-enumerated the seven-member families on 3 pts"],
        "3": ["clear: the wall is extending exact restoration to g=7"],
        "4": ["clear: the rank-three conjecture is motivated by Thm 2",
              "clear: the cross-trace lead follows from the equality"]},
        "reservations": []})
    v, err = theory_wake.parse_theory_verdict(text, criteria_keys=keys)
    assert err == "", err
    assert v["verdict"] == "pass"
    assert v["criticisms"] == []


def test_theory_verdict_still_refuses_mixed_and_bare_clear_bullets():
    """The relaxation is "several clears", not "anything goes": a
    criterion is one ruling, so clear+fired in the same criterion stays
    refused, and a bare `clear` among several stays refused too."""
    from Tooling.experiments import theory_wake

    mixed = json.dumps({"criteria": {
        "1": ["clear: the statement is on no record"],
        "2": ["clear: it implies main; the wall is Lemma 3"],
        "3": ["clear: the n<=5 census reproduces",
              "fired: the n=6 census could not be reproduced"]}})
    v, err = theory_wake.parse_theory_verdict(mixed)
    assert v is None and "mixes" in err

    bare = json.dumps({"criteria": {
        "1": ["clear: the statement is on no record"],
        "2": ["clear: it implies main; the wall is Lemma 3"],
        "3": ["clear: the n<=5 census reproduces", "clear"]}})
    v, err = theory_wake.parse_theory_verdict(bare)
    assert v is None and "bare" in err


def test_theory_verdict_parser_flattens_a_nested_bullet_list():
    """The other reasonable rendering of "a list per criterion, one
    bullet per objection": the bullets arrive one level deeper."""
    from Tooling.experiments import theory_wake

    text = json.dumps({"criteria": {
        "1": ["clear: the statement is on no record"],
        "2": ["clear: it implies main; the wall is Lemma 3"],
        "3": [["fired: the n=6 census could not be reproduced"]]}})
    v, err = theory_wake.parse_theory_verdict(text)
    assert err == ""
    assert v["criticisms"] == [
        "[criterion 3] the n=6 census could not be reproduced"]


def test_rejected_verdict_is_kept_never_deleted(tmp_path):
    """A verdict the parser refuses is the evidence for WHY it was
    refused: arm3h_r2 unlinked both tries, and the shape had to be dug
    out of the codex rollout afterwards. The file moves aside — into
    the attempts dir AND the runs dir — and a second rejection in the
    same round does not overwrite the first."""
    from Tooling.experiments import theory_wake

    proj = tmp_path / "attempts" / "review" / "r1"
    proj.mkdir(parents=True)
    out = tmp_path / "runs"
    vpath = proj / theory_wake.VERDICT_BASENAME

    first = '{"criteria": {"3": [{"verdict": "fired"}]}}'
    vpath.write_text(first, encoding="utf-8")
    kept = theory_wake.keep_rejected_verdict(vpath, round_no=1, out=out)
    assert kept.name == "verdict_r1_raw.json"
    assert kept.read_text(encoding="utf-8") == first
    assert (out / "verdict_r1_raw.json").read_text(encoding="utf-8") == first
    # gone from the contract path, so the next try cannot be read as a
    # verdict the judge did not write this time
    assert not vpath.exists()

    second = '{"criteria": {"3": 7}}'
    vpath.write_text(second, encoding="utf-8")
    kept2 = theory_wake.keep_rejected_verdict(vpath, round_no=1, out=out)
    assert kept2.name == "verdict_r1_raw2.json"
    assert kept.read_text(encoding="utf-8") == first
    assert (out / "verdict_r1_raw2.json").read_text(
        encoding="utf-8") == second


def test_rejected_verdict_log_line_names_the_offending_shape():
    """The log must say what the judge actually wrote — the type and
    shape per criterion — so a rejection is diagnosable from the run
    log without opening the rollout."""
    from Tooling.experiments import theory_wake

    text = json.dumps({"criteria": {
        "1": ["clear: on no record"],
        "3": [{"goal_id": 10670, "verdict": "fired", "reason": "x"}]},
        "reservations": []})
    line = theory_wake.describe_verdict_shape(text)
    assert '"1"' in line and "list[str]" in line
    assert '"3"' in line and "list[dict" in line
    assert "goal_id" in line and "verdict" in line and "reason" in line
    # unparseable bytes still describe themselves rather than throwing
    assert "not JSON" in theory_wake.describe_verdict_shape("{oops")


# ---------------------------------------------------------------------
# arms 5F / 5X — a four-criterion rubric on the same wake
# ---------------------------------------------------------------------

def test_a_fourth_criterion_is_ruled_on_not_dropped():
    """`theory5_judge.md` adjudicates FOUR (worth / rigour /
    load-bearing work / leads). Read against the three-criterion key
    set, criterion 4 is invisible: a fired objection is thrown away and
    the wake is told the document PASSED. The expected key set is
    therefore a parameter of the parse, declared per judge prompt."""
    from Tooling.experiments import theory_wake

    objection = ("the rank-three conjecture carries no test and does "
                 "not say what a counterexample would look like")
    text = json.dumps({"criteria": {
        "1": ["clear: the persistent-coordinate statement is on no record"],
        "2": ["clear: reran the n<=5 census, 1,171,932 families"],
        "3": ["clear: the wall is the chain step, attacked in Lemma 2"],
        "4": [f"fired: {objection}"]}})

    keys = theory_wake.criteria_keys_for(Path("x/theory5_judge.md"))
    assert keys == ("1", "2", "3", "4")
    v, err = theory_wake.parse_theory_verdict(text, criteria_keys=keys)
    assert err == ""
    assert v["verdict"] == "rebut"
    assert v["criticisms"] == [f"[criterion 4] {objection}"]
    # The failure this parameter exists to prevent, kept visible: the
    # three-criterion rubric reads the same bytes as an acceptance.
    assert theory_wake.parse_theory_verdict(text)[0]["verdict"] == "pass"


def test_a_four_criterion_rubric_refuses_a_missing_fourth():
    from Tooling.experiments import theory_wake

    text = json.dumps({"criteria": {
        "1": ["clear: on no record"],
        "2": ["clear: reran the census"],
        "3": ["clear: the wall is Lemma 3"]}})
    v, err = theory_wake.parse_theory_verdict(
        text, criteria_keys=("1", "2", "3", "4"))
    assert v is None
    assert "4" in err


def test_a_four_criterion_rubric_still_refuses_a_bare_clear():
    """The bare-clear refusal is the rubric's, not criterion 3's: it
    must fire on the fourth criterion too."""
    from Tooling.experiments import theory_wake

    text = json.dumps({"criteria": {
        "1": ["clear: on no record"],
        "2": ["clear: reran the census"],
        "3": ["clear: the wall is Lemma 3"],
        "4": ["clear"]}})
    v, err = theory_wake.parse_theory_verdict(
        text, criteria_keys=("1", "2", "3", "4"))
    assert v is None
    assert "bare" in err


def test_an_unregistered_judge_prompt_is_a_hard_error():
    """The key set is DECLARED per judge prompt, never counted out of
    the prompt text: a rubric that guesses reads a judge who skipped a
    criterion as a smaller rubric. A judge prompt nobody registered
    stops the wake instead of silently getting three."""
    from Tooling.experiments import theory_wake

    with pytest.raises(SystemExit, match="theory9_judge.md"):
        theory_wake.criteria_keys_for(Path("x/theory9_judge.md"))


# ---------------------------------------------------------------------
# run_matrix — what the first live matrix (2026-09-04) exposed
# ---------------------------------------------------------------------

def test_each_theory_arm_binds_its_own_author_and_judge_prompt():
    """Arms 5F and 5X differ ONLY in the author's prompt (fixed section
    shape vs. free), and both take the four-criterion judge. The arm is
    what names its two prompts; every named prompt must exist and its
    judge's rubric must be registered, or the arm would run against
    another arm's prompt while looking like it worked."""
    from Tooling.experiments import run_matrix, theory_wake

    assert run_matrix.ARMS["arm5F"].author_prompt == "theory5F.md"
    assert run_matrix.ARMS["arm5X"].author_prompt == "theory5X.md"
    for arm in ("arm5F", "arm5X"):
        assert run_matrix.ARMS[arm].judge_prompt == "theory5_judge.md"
        assert run_matrix.ARMS[arm].theory
    # arms 3 / 3h keep the prompts they ran with
    assert run_matrix.ARMS["arm3"].author_prompt == "theory.md"
    assert run_matrix.ARMS["arm3h"].judge_prompt == "theory_judge.md"
    for name, arm in run_matrix.ARMS.items():
        if not arm.theory:
            continue
        for rel in (arm.author_prompt, arm.judge_prompt):
            assert (run_matrix.DESIGN_DIR / rel).is_file(), f"{name}: {rel}"
        theory_wake.criteria_keys_for(arm.judge_prompt)


def test_command_for_passes_the_arms_own_prompts(tmp_path):
    from Tooling.experiments import run_matrix

    cmd = run_matrix.command_for("arm5X", tmp_path)
    assert cmd[cmd.index("--author-prompt") + 1] == \
        "theory_prompts/theory5X.md"
    assert cmd[cmd.index("--judge-prompt") + 1] == \
        "theory_prompts/theory5_judge.md"
    cmd3 = run_matrix.command_for("arm3h", tmp_path)
    assert cmd3[cmd3.index("--author-prompt") + 1] == \
        "theory_prompts/theory.md"
    assert "--hide-owner-notes" in cmd3


def test_overlay_gives_a_theory_arm_exactly_its_two_prompts(tmp_path):
    """The workspace gets the arm's own two files under
    `theory_prompts/` — and nothing else, so a stray prompt from
    another arm cannot be picked up by a mistyped path."""
    from Tooling.experiments import run_matrix

    applied = run_matrix.apply_overlay(tmp_path, "arm5F")
    assert sorted(applied) == ["theory_prompts/theory5F.md",
                               "theory_prompts/theory5_judge.md"]
    assert (tmp_path / "theory_prompts" / "theory5F.md").read_bytes() == \
        (run_matrix.DESIGN_DIR / "theory5F.md").read_bytes()
    assert not (tmp_path / "theory_prompts" / "theory.md").exists()


def test_the_run_record_says_which_snapshot_the_run_started_from(tmp_path):
    """The live state moves under the experiment — the daemon never
    stops — so a matrix launched after the first one is NOT at the same
    spacetime as it. When the copy was taken, and the Programme
    revision it carries, belong in each run's record."""
    from Tooling.experiments import run_matrix

    snap = tmp_path / "_snapshot.db"
    run_matrix.snapshot_meta_path(snap).write_text(json.dumps(
        {"snapshot": snap.as_posix(), "taken_utc": "2026-09-04T09:00:00+00:00",
         "group": 691, "programme_rev": 31, "goals": 812}), encoding="utf-8")
    rec = run_matrix.snapshot_record(snap)
    assert rec["taken_utc"] == "2026-09-04T09:00:00+00:00"
    assert rec["programme_rev"] == 31

def test_collect_binds_to_the_pipeline_the_run_itself_printed(tmp_path):
    """A scratch can hold more than one wake — arm3h_r2's did, after its
    first run died on a verdict rendering and was relaunched into the
    same workspace. Picking the NEWEST marker file then copies the wrong
    wake's artefacts over the right one's. The run's own log names the
    pipeline it created; that is the binding."""
    from Tooling.experiments import run_matrix

    ws = tmp_path / "scratch"
    mine, other = "11111111-1111-4111-8111-111111111111", \
                  "22222222-2222-4222-8222-222222222222"
    for pid, body in ((mine, "MINE"), (other, "OTHER")):
        d = ws / ".attempts" / pid
        d.mkdir(parents=True)
        (d / "theory_result.json").write_text(
            json.dumps({"pipeline_id": pid, "outcome": "accepted"}),
            encoding="utf-8")
        (d / "report.md").write_text(body, encoding="utf-8")
    # The other wake's marker is the NEWER one — mtime would choose it.
    os.utime(ws / ".attempts" / other / "theory_result.json",
             (time.time() + 60, time.time() + 60))

    run_dir = tmp_path / "runs" / "arm3h_r2"
    run_dir.mkdir(parents=True)
    (run_dir / "run.log").write_text(
        f"[theory] Combinatorics.union_closed g691 trigger='inject_batch_done' "
        f"pipeline={mine} attempts={ws / '.attempts' / mine}\n",
        encoding="utf-8")

    info = run_matrix.collect(ws, "arm3h", run_dir)
    assert info["attempts_dir"].endswith(mine)
    assert (run_dir / "report.md").read_text(encoding="utf-8") == "MINE"
