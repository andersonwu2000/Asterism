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

Nothing here spells a criterion's MEANING out either. The rubric has
been reordered and renamed more than once, and a test that writes
"Reachability" down is a second copy of the rubric that has to be
hand-edited every time — which is how a criterion's name and its rule
drift apart in the first place. Every assertion below reads the
prompt's own words and pins the STRUCTURE that must hold whatever
those words become.
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
    """The whole `n. **<Name>**: …` line, found by NUMBER — never by
    the name, which is what changes."""
    return next(ln for ln in TEXT.splitlines()
                if re.match(rf"^{re.escape(n)}\.\s+\*\*", ln))


def _naming_rule_halves() -> "list[str]":
    """The two halves of the prompt's "…'s reason IS the naming: A, and
    B." sentence."""
    m = re.search(r"'s reason IS the naming:\s*(.+?)\.\s*$", TEXT, re.M)
    assert m, "the prompt no longer spells out what the naming must say"
    return [h.strip() for h in m.group(1).split(", and ")]


def _template_naming_entry() -> str:
    """The output template's `clear: …` entry for the naming criterion,
    as the judge copies it."""
    tmpl = TEXT.split("```json", 1)[1].split("```", 1)[0]
    m = re.search(rf'"{re.escape(adversary.NAMING_CRITERION)}"\s*:\s*'
                  r'\[\s*"(clear:[^"]*)"', tmpl)
    assert m, ("the output template no longer shows a `clear:` entry on "
               f"criterion {adversary.NAMING_CRITERION}")
    return m.group(1)


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


def test_the_naming_criterion_is_the_one_about_reaching_the_claim() -> None:
    """Which criterion carries the naming is not arbitrary: the naming
    is about the route to the MAIN claim, so it belongs to a criterion
    whose own line judges the route against that claim. Pinned by what
    the line SAYS, not by the name it currently wears — the name has
    been reassigned twice and the obligation did not move with it."""
    line = _criterion_line(adversary.NAMING_CRITERION)
    assert "MAIN claim" in line, (
        f"criterion {adversary.NAMING_CRITERION} carries the naming but "
        f"its own line no longer judges anything against the MAIN "
        f"claim:\n{line}")
    assert _criteria_in_prompt()[adversary.NAMING_CRITERION], (
        "the naming criterion lost its name")


def test_the_output_template_puts_the_naming_on_that_criterion() -> None:
    """The template is what a judge copies. If it shows the naming on a
    different number than the rule demands, the example loses — the
    same failure the strategist prompts had with `brief`/`proof`.

    And the template must demonstrate the rule it illustrates: the
    rule's first half is the template's first placeholder, verbatim. A
    reworded criterion that updates one and not the other hands the
    judge two different jobs under one number."""
    entry = _template_naming_entry()          # asserts the number itself
    first_half = _naming_rule_halves()[0]
    assert entry.startswith(f"clear: <{first_half}>"), (
        f"the rule asks for {first_half!r} first; the template's first "
        f"placeholder is {entry!r}")
    # Two placeholders, em-dash separated — the shape the parser's
    # refusal message quotes back at a judge that clears this bare.
    assert entry.count("<") == 2 and " — " in entry, entry


def test_the_bare_clear_refusal_quotes_the_prompts_own_template() -> None:
    """The refusal is the judge's ONLY instruction at the moment its
    verdict is thrown away, so it must name the shape THIS rubric asks
    for. Written as a literal it kept describing the pre-reword
    criterion, and a gate naming an action the prompt no longer
    describes is a gate the agent cannot obey (memory:
    `gate_must_name_a_reachable_action`)."""
    import json
    shape = adversary.naming_clear_shape()
    assert shape in TEXT, (
        f"`naming_clear_shape()` is not quoting the prompt: {shape!r} "
        f"does not appear in adversary.md")
    bare = {k: "clear: holds here" for k in adversary.CRITERIA_KEYS}
    bare[adversary.NAMING_CRITERION] = "clear"
    v, err = adversary.parse_verdict(json.dumps({"criteria": bare}))
    assert v is None
    assert shape in err, (
        f"the refusal must show the rubric's own way out; got {err!r}")


def test_the_refusal_follows_the_rubric_when_it_is_reworded(
        monkeypatch) -> None:
    """The one that proves DERIVATION rather than coincidence: reword
    the template and the way out must reword with it. A literal passes
    the test above on the day it is written and fails every reader
    afterwards."""
    import json
    reworded = TEXT.replace(
        _template_naming_entry(),
        "clear: <the reworded first half> — <the reworded second half>")
    monkeypatch.setattr(adversary, "_prompt_text", lambda: reworded)
    bare = {k: "clear: holds here" for k in adversary.CRITERIA_KEYS}
    bare[adversary.NAMING_CRITERION] = "clear"
    _v, err = adversary.parse_verdict(json.dumps({"criteria": bare}))
    assert "<the reworded first half>" in err, (
        f"the refusal ignored the rubric it is supposed to quote: {err!r}")


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
    """The naming criterion refuses a route that runs against the
    verified Programme record — the case the pre-08-13 wording missed,
    because such a route was never WALKED and so never "failed".
    union_closed had kernel-verified that reaching 1/2 must exploit
    exact closure; a proposal denying that should die at the gate rather
    than after the machine time.

    Pinned on the RECORD, not on the sentence that mentions it: the
    clause is rewritten whenever the criterion is, and the refusal is
    the thing that has to survive the rewording.

    The explicit override-path sentence ("overridden by proof, not
    conjecture") was retired in the owner's 2026-08-18 finalized
    wording; the honesty criterion's "a mathematical claim must rest on
    a complete argument, never on conjecture" carries the proof-not-
    conjecture standard now."""
    line = _criterion_line(adversary.NAMING_CRITERION)
    assert "record" in line, (
        "the route criterion no longer refuses a route the record has "
        f"already settled:\n{line}")
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


def test_the_route_clause_keeps_all_of_its_refusals() -> None:
    """Adding a refusal must not quietly drop another. The clause has
    listed three since 2026-08-13; what is pinned is that three are
    still there and still say what is NOT ALLOWED, not which words say
    it — a rewrite that comes back with two is a route the gate stops
    catching, and that is what this has to catch."""
    line = _criterion_line(adversary.NAMING_CRITERION)
    refusal = line.rsplit(". ", 1)[-1]
    assert refusal.rstrip().endswith("is not allowed."), (
        f"the route criterion no longer closes with a refusal:\n{line}")
    items = [p for p in refusal.split(", ")
             if p.strip() and not p.startswith("is not allowed")]
    assert len(items) >= 3, (
        f"the route clause is down to {len(items)} refusal(s); it has "
        f"listed three since 2026-08-13:\n{refusal}")
    assert any(p.startswith("or ") for p in items), refusal


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
