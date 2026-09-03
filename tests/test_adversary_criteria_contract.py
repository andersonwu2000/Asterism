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

2026-09-04 (owner ruling, after the theory-wake experiment) changed
what criterion 2 ASKS, not where it sits: Reachability became
**Relation** — the Roadmap must state the statement this Programme
works toward and how it stands to the MAIN claim (implies / equivalent
/ reduces / refuting condition), argued rather than asserted. The
"stops short of it" refusal went with it, because a Programme that
honestly reduces the claim always stops short; what replaces it is the
wrong-direction refusal and the requirement that a named load-bearing
difficulty be ATTACKED somewhere concrete. The pins below track the new
question; they are a requirement change, not a fix.
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


def _criterion_line(n: str) -> str:
    """The one rubric line for criterion `n`, found by its number rather
    than by its name — so a rename does not turn the pin vacuous."""
    line = next((ln for ln in TEXT.splitlines()
                 if _CRITERION.match(ln) and ln.startswith(f"{n}.")), None)
    assert line, f"the prompt no longer states a criterion {n}"
    return line


def test_the_prompt_still_declares_five_numbered_criteria() -> None:
    """A regex that matched nothing would make the rest vacuous."""
    found = _criteria_in_prompt()
    assert set(found) == set(adversary.CRITERIA_KEYS), (
        f"prompt declares {sorted(found)}, parser expects "
        f"{sorted(adversary.CRITERIA_KEYS)}")


def test_the_naming_rule_names_the_same_criterion_in_both_places() -> None:
    """The exact drift the renumber nearly shipped. Since 2026-08-29 the
    bare-clear ban is five-wide, so the prompt states the general rule
    plus which criterion's reason IS the naming — both halves must track
    the parser."""
    assert "No criterion takes a bare `clear`" in TEXT, (
        "the prompt no longer states the five-wide bare-clear rule the "
        "parser enforces")
    m = re.search(r"Criterion (\d)'s reason IS the naming", TEXT)
    assert m, ("the prompt no longer says whose reason is the naming — "
               "if it moved, move `NAMING_CRITERION` with it")
    assert m.group(1) == adversary.NAMING_CRITERION, (
        f"prompt hangs the naming on criterion {m.group(1)}; the parser "
        f"enforces it on {adversary.NAMING_CRITERION}. A judge obeying "
        f"the prompt would have its verdict refused.")


def test_the_naming_criterion_is_the_one_about_the_relation_to_the_claim() -> None:
    """Which criterion carries the naming is not arbitrary: the line it
    must carry is the statement worked toward AND how it stands to the
    MAIN claim, so it belongs to the criterion that judges that relation
    (`Relation` since the owner's 2026-09-04 ruling; `Reachability`
    before it)."""
    named = _criteria_in_prompt()[adversary.NAMING_CRITERION]
    assert named == "Relation", (
        f"criterion {adversary.NAMING_CRITERION} is now {named!r}; the "
        f"naming obligation belongs to the criterion that judges the "
        f"relation to the MAIN claim")
    line = _criterion_line(adversary.NAMING_CRITERION)
    assert "how it stands to the MAIN claim" in line, (
        "the naming criterion no longer asks for the relation to the "
        "MAIN claim — the naming it demands would have nothing to name")


def test_the_output_template_puts_the_naming_on_that_criterion() -> None:
    """The template is what a judge copies. If it shows the naming on a
    different number than the rule demands, the example loses — the
    same failure the strategist prompts had with `brief`/`proof`."""
    tmpl = TEXT.split("```json", 1)[1].split("```", 1)[0]
    # 2026-08-28: criteria take LISTS (one bullet per objection) — the
    # naming shape sits inside the list brackets now.
    # 2026-09-04: the shape names three things, not two — the statement
    # worked toward, its relation to the MAIN claim, and where the
    # load-bearing difficulty is attacked.
    m = re.search(r'"(\d)":\s*\["clear: <the statement this Programme '
                  r'works toward and its relation to the MAIN claim> — '
                  r'<where the load-bearing difficulty is attacked>"\]',
                  tmpl)
    assert m, "the template no longer shows the naming shape at all"
    assert m.group(1) == adversary.NAMING_CRITERION, (
        f"the template demonstrates the naming on criterion {m.group(1)} "
        f"but the parser enforces it on {adversary.NAMING_CRITERION}")


def test_the_parser_actually_refuses_a_bare_clear_there() -> None:
    """Behavioural, so the constant cannot drift away from the code that
    reads it."""
    import json
    n = adversary.NAMING_CRITERION
    bare = {k: "clear: holds here" for k in adversary.CRITERIA_KEYS}
    bare[n] = "clear"
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

    The boundary is SUBJECT (mathematics and route vs bookkeeping).
    The owner's 2026-08-18 finalized wording restates it as one rule
    and RETIRES the explicit "unless its underlying fact fails
    checking" escape hatch: a wrong pointer or a false claim now fires
    through criterion 5's own text (node pointers, complete argument),
    not through a rider on the boundary rule. Reservations must also
    never patch over a fired criterion."""
    assert ("Bookkeeping or format defects, and redundant Programme "
            "content, do not rebut") in TEXT
    assert "a reservation must not be used to patch over one" in TEXT
    assert "A defect you can name belongs on its criterion's line" \
        not in TEXT, "the superseded sentence is still there, contradicting"


def test_a_verified_record_still_refuses_a_contradicting_route() -> None:
    """Criterion 2 refuses a route that contradicts a verified Programme
    record — the case the pre-08-13 wording missed, because such a route
    was never WALKED and so never "failed". union_closed had
    kernel-verified that reaching 1/2 must exploit exact closure; a
    proposal denying that should die at the gate rather than after the
    machine time.

    The explicit override-path sentence ("overridden by proof, not
    conjecture") was retired in the owner's 2026-08-18 finalized
    wording; criterion 5's "a mathematical claim must rest on a
    complete argument, never on conjecture" carries the proof-not-
    conjecture standard now."""
    assert "a contradiction of a verified Programme record" in \
        _criterion_line(adversary.NAMING_CRITERION)
    assert "never on conjecture" in TEXT


def test_the_finalized_wording_keeps_its_new_anchors() -> None:
    """The owner's 2026-08-18 revision retired several prose clauses;
    these three are the replacements that carry their load, pinned so a
    later trim does not silently drop them too: the failure modes still
    route through criterion 1, same-batch bricks stay independent, and
    reservations cannot launder a fired criterion."""
    assert "rejected through criterion 1" in TEXT
    assert "must not cite each other" in TEXT
    assert "patch over" in TEXT


def test_the_relation_clause_keeps_its_refusals_and_defines_attacked() -> None:
    """Rewriting the clause must not quietly drop the refusals that
    survived it.

    The owner's 2026-09-04 wording retires "stops short of it" — a
    Programme that honestly REDUCES the MAIN claim stops short of it by
    construction, so that refusal fought the new question. The two that
    remain are re-walking and the verified-record contradiction. The
    added refusal (naming a load-bearing difficulty and attacking it
    nowhere) is only enforceable because the clause defines what an
    attack is; without that sentence a judge would take the AHEAD
    mention as the attack, which is the disease the ruling removed."""
    line = _criterion_line(adversary.NAMING_CRITERION)
    assert "a route re-walked unchanged" in line
    assert "a contradiction of a verified Programme record" in line
    assert ("attacked = a NOW brick bites it, or the Proof carries an "
            "argument or a counterexample on it; a name in AHEAD is not "
            "an attack") in line, (
        "the clause no longer says what counts as attacking the "
        "load-bearing difficulty — the refusal it gates is unjudgeable")
    assert "stops short of it" not in line, (
        "the retired refusal is back, contradicting a Roadmap that "
        "reduces the MAIN claim rather than closing it")


def test_every_criterion_refuses_a_bare_clear() -> None:
    """2026-08-29 (calibration survey): the reason requirement went
    five-wide — 70-94% of clears on the unforced criteria were the bare
    word, and the survey's rule-position experiment proved reasons
    appear only where the parser demands them. Refusal must name the
    criterion and show the way out."""
    import json
    for k in adversary.CRITERIA_KEYS:
        crit = {c: "clear: holds here" for c in adversary.CRITERIA_KEYS}
        crit[adversary.NAMING_CRITERION] = "clear: entry — distance"
        crit[k] = "clear"
        v, err = adversary.parse_verdict(json.dumps({"criteria": crit}))
        assert v is None, f"bare clear on {k} must be refused"
        assert f"criterion {k}" in err and "clear:" in err
