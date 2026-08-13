"""The judge's prompt and the verdict parser must agree on the numbers.

Five criteria live in two places at once: `adversary.md` tells the judge
what each number means and which one may not take a bare `clear`, and
`pipeline/adversary.parse_verdict` refuses the verdict when that rule is
broken. The prompt is the instruction; the parser is the enforcement.

2026-08-13 renumbered them — Value became 1 and Reachability became 2,
so that necessity is judged before sufficiency and the naming
obligation sits with the criterion that asks whether the route reaches
the MAIN claim. The plan for that change moved the prompt sentence and
left the parser matching on `"1"`. Landed as written, a judge obeying
the new prompt would put its naming on criterion 2, leave 1 a bare
`clear`, and have the whole verdict refused as malformed — a wasted
Adversary round per proposal, on the gate that decides what lands.

So the pin below is not "the prompt says 2". It is that the prompt and
the parser say the SAME thing, derived from each side rather than from
a constant repeated here.
"""
from __future__ import annotations

import re
from pathlib import Path

from Tooling.pipeline import adversary

PROMPT = (Path(__file__).resolve().parents[1] / "Tooling" / "prompts"
          / "adversary" / "adversary.md")
TEXT = PROMPT.read_text(encoding="utf-8")

#: `1. **Value**: …` — the numbered criteria, in file order.
_CRITERION = re.compile(r"^(\d)\.\s+\*\*([^*]+)\*\*:", re.M)


def _criteria_in_prompt() -> "dict[str, str]":
    return {n: name.strip() for n, name in _CRITERION.findall(TEXT)}


def test_the_prompt_still_declares_five_numbered_criteria() -> None:
    """A regex that matched nothing would make the rest vacuous."""
    found = _criteria_in_prompt()
    assert set(found) == set(adversary.CRITERIA_KEYS), (
        f"prompt declares {sorted(found)}, parser expects "
        f"{sorted(adversary.CRITERIA_KEYS)}")


def test_the_naming_rule_names_the_same_criterion_in_both_places() -> None:
    """The exact drift the renumber nearly shipped."""
    m = re.search(r"Criterion (\d) never takes a bare `clear`", TEXT)
    assert m, ("the prompt no longer states the bare-clear rule — if it "
               "moved, move `NAMING_CRITERION` with it")
    assert m.group(1) == adversary.NAMING_CRITERION, (
        f"prompt says criterion {m.group(1)} may not take a bare "
        f"`clear`; the parser enforces it on "
        f"{adversary.NAMING_CRITERION}. A judge obeying the prompt "
        f"would have its verdict refused.")


def test_the_naming_criterion_is_the_one_about_reaching_the_claim() -> None:
    """Which criterion carries the naming is not arbitrary: the line it
    must carry is "the entry that closes the MAIN claim", so it belongs
    to the criterion that judges whether the route gets there."""
    assert _criteria_in_prompt()[adversary.NAMING_CRITERION] == "Reachability"


def test_the_output_template_puts_the_naming_on_that_criterion() -> None:
    """The template is what a judge copies. If it shows the naming on a
    different number than the rule demands, the example loses — the
    same failure the strategist prompts had with `brief`/`proof`."""
    tmpl = TEXT.split("```json", 1)[1].split("```", 1)[0]
    m = re.search(r'"(\d)":\s*"clear: <the entry that closes', tmpl)
    assert m, "the template no longer shows the naming shape at all"
    assert m.group(1) == adversary.NAMING_CRITERION, (
        f"the template demonstrates the naming on criterion {m.group(1)} "
        f"but the parser enforces it on {adversary.NAMING_CRITERION}")


def test_the_parser_actually_refuses_a_bare_clear_there() -> None:
    """Behavioural, so the constant cannot drift away from the code that
    reads it."""
    import json
    n = adversary.NAMING_CRITERION
    bare = {k: "clear" for k in adversary.CRITERIA_KEYS}
    v, err = adversary.parse_verdict(json.dumps({"criteria": bare}))
    assert v is None and f"criterion {n}" in (err or ""), (
        f"a bare clear on {n} must be refused; got {err!r}")
    named = dict(bare)
    named[n] = "clear: the closure entry — two lemmas still stand"
    v, err = adversary.parse_verdict(json.dumps({"criteria": named}))
    assert v is not None, f"a NAMED clear on {n} must be accepted: {err}"


# ─── fired vs reservation, and the verified-record clause ────────────
#
# Two sentences the judge is graded by, each of which had to be written
# twice before it held. They are pinned WITH their escape hatch: a rule
# that forbids something without naming the way out is the failure mode
# this repo keeps paying for.


def test_the_fired_reservation_boundary_is_substantive() -> None:
    """It used to be "a defect you can name belongs on its criterion's
    line", which collided head-on with "reservations: only for concerns
    that fire no criterion" — every nameable defect had to rebut the
    whole batch, so a misnumbered heading cost a round. Judges reported
    the collision twice on 2026-08-12.

    The boundary is now about SUBJECT (mathematics and route vs
    bookkeeping), with the leak sealed: a format defect whose underlying
    fact will not check is not bookkeeping, it is honesty."""
    assert "Fired is for the mathematics and the route" in TEXT
    assert "bookkeeping or format defect is a reservation" in TEXT
    assert "unless its underlying fact fails checking" in TEXT, (
        "without this clause a wrong number could be filed as a "
        "presentation nit — the check is what tells the two apart")
    assert "A defect you can name belongs on its criterion's line" \
        not in TEXT, "the superseded sentence is still there, contradicting"


def test_a_verified_record_can_be_contradicted_only_by_proof() -> None:
    """Criterion 2 refuses a route that contradicts a verified Programme
    record — the case the old wording missed, because such a route was
    never WALKED and so never "failed". union_closed had kernel-verified
    that reaching 1/2 must exploit exact closure; a proposal denying that
    should die at the gate rather than after the machine time.

    Pinned together with its escape hatch, deliberately: a criterion
    that forbids without naming a way out teaches the author to hide the
    contradiction instead of overturning the record."""
    crit2 = _CRITERION.sub(lambda m: m.group(0), TEXT)  # keep TEXT intact
    assert "contradicts a verified Programme record" in crit2
    assert "A verified record is overridden by proof, not conjecture." \
        in TEXT, "the override path must be stated, not implied"


def test_the_route_clause_kept_its_two_original_refusals() -> None:
    """Adding a third refusal must not quietly drop the first two."""
    line = next(ln for ln in TEXT.splitlines()
                if ln.startswith("2. **Reachability**"))
    assert "stops short of it" in line
    assert "re-walks a failed route unchanged" in line
    assert "contradicts a verified Programme record" in line


def test_every_other_criterion_still_takes_a_bare_clear() -> None:
    """The rule is one criterion's, not a general tax on brevity."""
    import json
    n = adversary.NAMING_CRITERION
    for k in adversary.CRITERIA_KEYS:
        if k == n:
            continue
        crit = {c: "clear" for c in adversary.CRITERIA_KEYS}
        crit[n] = "clear: entry — distance"
        crit[k] = "clear"
        v, err = adversary.parse_verdict(json.dumps({"criteria": crit}))
        assert v is not None, f"bare clear on {k} should pass: {err}"
