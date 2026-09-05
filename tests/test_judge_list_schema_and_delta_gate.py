"""The judge answers in lists, and a byte-identical resubmission never
reaches him (owner designs 2026-08-28).

Forensics behind both: the one-string-per-criterion schema bound in
4,495/4,495 rounds — a judge with three defects under one criterion
dripped them one round each — and every byte-identical debate on
record traces to the zen resume-amnesia era (the revision turn
succeeded but never touched the file), so the delta gate is an
accident guard, not author discipline."""
import json

from Tooling.pipeline import adversary


def _verdict(criteria):
    base = {k: ["clear: holds for this batch"]
            for k in adversary.CRITERIA_KEYS}
    for n in adversary.NAMING_CRITERIA:
        base[n] = ["clear: the closure entry — two lemmas still stand"]
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


def test_clear_takes_as_many_bullets_as_the_criterion_has_items() -> None:
    """Requirement change 2026-09-05: criterion 1 rules one line per NOW
    Inject, so a clear criterion carries one bullet per item and the
    old "clear takes exactly one entry" refused the shape the rubric
    asks for — six union_closed wakes died on it. Every bullet still
    carries its own reason."""
    v, err = adversary.parse_verdict(_verdict({
        "4": ["clear: checked", "clear — checked twice"]}))
    assert v is not None, err
    assert v["verdict"] == "pass"
    v, err = adversary.parse_verdict(_verdict({
        "4": ["clear: checked", "clear"]}))
    assert v is None and "criterion 4" in err


def test_the_legacy_single_string_form_still_parses() -> None:
    base = {k: "clear: holds here" for k in adversary.CRITERIA_KEYS}
    for n in adversary.NAMING_CRITERIA:
        base[n] = "clear: the entry — one gap"
    base["1"] = "fired: a load-bearing objection"
    v, err = adversary.parse_verdict(json.dumps({"criteria": base}))
    assert v is not None, err
    assert v["criticisms"] == ["[criterion 1] a load-bearing objection"]


def test_the_naming_rule_survives_the_list_form() -> None:
    for n in adversary.NAMING_CRITERIA:
        v, err = adversary.parse_verdict(_verdict({n: ["clear"]}))
        assert v is None and n in err




# ------------------------------- native_decide soft confirm gate

def test_the_rebuttal_never_carries_the_native_decide_notice() -> None:
    """The rebuttal's over-length escalation ends "The revision must
    come back smaller." — true of a bloated proposal, nonsense as an
    answer to a `native_decide` mention. Before 2026-09-04 the notice
    rode `length_warn` into exactly that sentence. The judge still
    reads both (they are joined for its projection); the rebuttal takes
    the length warning alone."""
    from Tooling.state import programme
    from Tooling.pipeline.strategist.wake import _format_rebuttal

    verdict = {"criticisms": ["[criterion 2] the step is unproven"]}
    notice = programme.native_decide_warning("plan: native_decide")
    assert notice is not None

    # Only the notice tripped → the rebuttal says nothing about size.
    reb = _format_rebuttal(verdict, 1, 2, length_warn=None)
    assert "NATIVE_DECIDE" not in reb
    assert "come back smaller" not in reb

    # A real length warning still escalates, and still alone.
    length = "⚠ PROOF LENGTH WARNING: 99999 chars"
    reb = _format_rebuttal(verdict, 1, 2, length_warn=length)
    assert length in reb and "come back smaller" in reb
    assert "NATIVE_DECIDE" not in reb

    # …and the judge's own line is the two joined, either side optional.
    from Tooling.pipeline.strategist.wake import _judge_warning
    assert _judge_warning(None, None) is None
    assert _judge_warning(length, None) == length
    assert _judge_warning(None, notice) == notice
    assert _judge_warning(length, notice) == length + "\n" + notice
