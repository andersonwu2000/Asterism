"""The judge answers in lists, and a byte-identical resubmission never
reaches him (owner designs 2026-08-28).

Forensics behind both: the one-string-per-criterion schema bound in
4,495/4,495 rounds — a judge with three defects under one criterion
dripped them one round each — and every byte-identical debate on
record traces to the zen resume-amnesia era (the revision turn
succeeded but never touched the file), so the delta gate is an
accident guard, not author discipline."""
import json
import re
from pathlib import Path

from Tooling.pipeline import adversary


def _verdict(criteria):
    base = {k: ["clear: holds for this batch"]
            for k in adversary.CRITERIA_KEYS}
    base[adversary.NAMING_CRITERION] = [
        "clear: the closure entry — two lemmas still stand"]
    base.update(criteria)
    return json.dumps({"criteria": base})


def test_a_criterion_takes_many_bullets_and_all_of_them_fire() -> None:
    v, err = adversary.parse_verdict(_verdict({
        "3": ["fired: the derivative in step 4 is wrong",
              "fired: step 7 divides by a quantity not shown nonzero",
              "fired: the induction base n=2 is unproven"]}))
    assert v is not None, err
    assert v["verdict"] == "rebut"
    threes = [c for c in v["criticisms"] if c.startswith("[criterion 3]")]
    assert len(threes) == 3, threes


def test_mixed_clear_and_fired_in_one_criterion_is_refused() -> None:
    v, err = adversary.parse_verdict(_verdict({
        "3": ["fired: a defect", "clear: rest holds"]}))
    assert v is None and "one or the other" in err


def test_clear_takes_exactly_one_entry() -> None:
    v, err = adversary.parse_verdict(_verdict({
        "4": ["clear: checked", "clear — checked twice"]}))
    assert v is None and "exactly one" in err


def test_the_legacy_single_string_form_still_parses() -> None:
    base = {k: "clear: holds here" for k in adversary.CRITERIA_KEYS}
    base[adversary.NAMING_CRITERION] = "clear: the entry — one gap"
    base["1"] = "fired: a load-bearing objection"
    v, err = adversary.parse_verdict(json.dumps({"criteria": base}))
    assert v is not None, err
    assert v["criticisms"] == ["[criterion 1] a load-bearing objection"]


def test_the_naming_rule_survives_the_list_form() -> None:
    v, err = adversary.parse_verdict(_verdict(
        {adversary.NAMING_CRITERION: ["clear"]}))
    assert v is None and adversary.NAMING_CRITERION in err


def test_the_prompt_teaches_the_list_shape() -> None:
    text = Path("Tooling/prompts/adversary/adversary.md").read_text(
        encoding="utf-8")
    assert "a list per criterion, one bullet per objection" in text
    assert '"fired: <another objection under this criterion>"' in text


def test_the_delta_gate_bounces_identical_bodies_before_the_judge() -> None:
    """Source pins: the gate compares against the body the judge last
    rejected, skips the judge on identity, discards at three
    consecutive no-deltas, and books the rejected body at the rebut
    point."""
    src = Path("Tooling/pipeline/strategist/wake.py").read_text(
        encoding="utf-8")
    assert "proposal_body == _last_judged" in src
    assert "judge skipped" in src
    assert "_no_delta >= 3" in src
    assert 'channel="strategist_no_delta"' in src
    assert re.search(r"err_is_rebuttal = True\s*\n\s*# delta-gate "
                     r"bookkeeping", src), (
        "the rebut point must record _last_judged/_last_rebuttal")
    # the bounce message names the reachable action
    assert "edit proposal.md" in src
