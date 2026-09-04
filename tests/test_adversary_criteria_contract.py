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


def _naming_rules() -> "dict[str, str]":
    """`{criterion: what its clear must name}` — every "Criterion N's
    reason IS the naming: …" sentence the prompt states.

    There is more than one as of v6 (d5916446): criterion 1's reason is
    each NOW Inject's consumption chain and endpoint, criterion 2's is
    the Relation's argument and the handling of the wall. Read as a
    SET, never as "the naming criterion" — how many there are is the
    rubric's to decide, and the parser has to enforce exactly them."""
    rules = {n: clause.strip() for n, clause in re.findall(
        r"Criterion (\d)'s reason IS the naming:\s*(.+?)\.(?:\s|$)", TEXT)}
    assert rules, ("the prompt no longer says whose reason is the "
                   "naming — if it moved, move `NAMING_CRITERIA` with it")
    return rules


def _template_naming_entry(n: str) -> str:
    """The output template's `clear: …` entry for criterion `n`, as the
    judge copies it."""
    tmpl = TEXT.split("```json", 1)[1].split("```", 1)[0]
    m = re.search(rf'"{re.escape(n)}"\s*:\s*\[\s*"(clear:[^"]*)"', tmpl)
    assert m, ("the output template no longer shows a `clear:` entry on "
               f"criterion {n}")
    return m.group(1)


def _subjects(text: str) -> "set[str]":
    """The things a clause names, crudely stemmed: every word of four
    letters or more, cut to its first four.

    Crude ON PURPOSE. What has to agree between a naming rule and the
    template that illustrates it is the SUBJECTS the judge must name,
    not the words used for them — v6 asks for "the handling of the
    wall" in the rule and "how this batch handles it" in the template,
    and a verbatim pin would have to be hand-edited on every reword,
    which is how the two sides drift apart in the first place."""
    return {w.lower()[:4] for w in re.findall(r"[A-Za-z']{4,}", text)}


def _route_criterion() -> str:
    """The numbered criterion that judges the ROUTE — found by what its
    line does, never by its number or its name (both have been
    reassigned, and the obligation did not move with either). Exactly
    one criterion holds that job; two would mean the rubric has grown a
    second, unpinned copy of it."""
    hits = [n for n in sorted(_criteria_in_prompt())
            if "route" in _criterion_line(n).lower()]
    assert len(hits) == 1, (
        f"expected exactly one criterion judging the route, found "
        f"{hits or 'none'}")
    return hits[0]


def _citation_criterion() -> str:
    """The numbered criterion that demands citations — where the
    fired/reservation boundary sends an assertion that lost its."""
    hits = [n for n in sorted(_criteria_in_prompt())
            if "citation" in _criterion_line(n).lower()]
    assert len(hits) == 1, (
        f"expected exactly one criterion demanding citations, found "
        f"{hits or 'none'}")
    return hits[0]


def _reference_point_words() -> "list[str]":
    """The names the prompt itself declares mean its fixed reference
    point. Read, not written down here: v6 states criterion 1 in the
    charter's words where v5 said "MAIN claim", and the prompt's own
    sentence is what says the two mean the same thing."""
    m = re.search(r"The fixed reference point[^.]*?every (.+?) "
                  r"in the criteria mean it", TEXT)
    assert m, "the prompt no longer declares its fixed reference point"
    words = re.findall(r'"([^"]+)"', m.group(1))
    assert words, m.group(1)
    return words


def test_the_prompt_still_declares_five_numbered_criteria() -> None:
    """A regex that matched nothing would make the rest vacuous."""
    found = _criteria_in_prompt()
    assert set(found) == set(adversary.CRITERIA_KEYS), (
        f"prompt declares {sorted(found)}, parser expects "
        f"{sorted(adversary.CRITERIA_KEYS)}")


def test_the_naming_rule_names_the_same_criterion_in_both_places() -> None:
    """The exact drift the renumber nearly shipped. Since 2026-08-29 the
    bare-clear ban is five-wide, so the prompt states the general rule
    plus whose reason IS the naming — every half must track the parser.

    v6 (d5916446) hangs a naming on TWO criteria: the consumption chain
    with its endpoint (1), and the Relation with the handling of the
    wall (2). Both directions cost a round: a criterion the parser
    demands and the prompt does not refuses a judge that obeyed its
    rubric, and a criterion the prompt demands and the parser does not
    is a naming that quietly stops being written."""
    assert "No criterion takes a bare `clear`" in TEXT, (
        "the prompt no longer states the five-wide bare-clear rule the "
        "parser enforces")
    named = set(_naming_rules())
    assert named == set(adversary.NAMING_CRITERIA), (
        f"prompt hangs the naming on {sorted(named)}; the parser "
        f"enforces it on {sorted(adversary.NAMING_CRITERIA)}. A judge "
        f"obeying the prompt has its verdict refused, or clears a "
        f"naming criterion bare and is not caught.")


def test_the_naming_criterion_is_the_one_about_reaching_the_claim() -> None:
    """Which criteria carry the naming is not arbitrary: the naming is
    about the route reaching the claim this judgment settles, so it
    belongs to criteria whose own line judges something against that
    claim. Pinned by what the line SAYS, not by the name it currently
    wears — the name has been reassigned twice and the obligation did
    not move with it.

    Which WORDS name that claim is read from the prompt too: v6 states
    criterion 1 in terms of the charter where v5 said "MAIN claim", and
    the prompt's own "What you see" declares the two mean the one fixed
    reference point."""
    points = _reference_point_words()
    for n in sorted(_naming_rules()):
        line = _criterion_line(n)
        assert any(p in line for p in points), (
            f"criterion {n} carries the naming but its own line no "
            f"longer judges anything against "
            f"{' / '.join(points)}:\n{line}")
        assert _criteria_in_prompt()[n], "a naming criterion lost its name"


def test_the_output_template_puts_the_naming_on_that_criterion() -> None:
    """The template is what a judge copies. If it shows the naming on a
    different number than the rule demands, the example loses — the
    same failure the strategist prompts had with `brief`/`proof`.

    And each template entry must demonstrate the rule it illustrates:
    EVERY subject the rule names appears in the placeholder the judge
    copies. A reworded criterion that updates one and not the other
    hands the judge two different jobs under one number.

    v5 pinned the rule's first half verbatim and its second half only
    as a placeholder count; v6 words the two sides differently ("the
    handling of the wall" against "how this batch handles it"), so the
    pin moved onto the subjects — and it now covers the whole rule
    instead of its first half."""
    for n, clause in sorted(_naming_rules().items()):
        entry = _template_naming_entry(n)     # asserts the number itself
        assert "<" in entry, (
            f"criterion {n}'s template entry shows the judge no "
            f"placeholder to fill: {entry!r}")
        dropped = _subjects(clause) - _subjects(entry)
        assert not dropped, (
            f"criterion {n}'s rule asks the judge to name {clause!r}; "
            f"the template's entry {entry!r} drops {sorted(dropped)}")


def test_the_bare_clear_refusal_quotes_the_prompts_own_template() -> None:
    """The refusal is the judge's ONLY instruction at the moment its
    verdict is thrown away, so it must name the shape THIS rubric asks
    for. Written as a literal it kept describing the pre-reword
    criterion, and a gate naming an action the prompt no longer
    describes is a gate the agent cannot obey (memory:
    `gate_must_name_a_reachable_action`).

    Per naming criterion, since v6: the two ask for different namings
    (a consumption chain, a Relation and its wall), so one shared way
    out would send half the refusals to the wrong job."""
    import json
    for n in sorted(_naming_rules()):
        shape = adversary.naming_clear_shape(n)
        assert shape in TEXT, (
            f"`naming_clear_shape({n!r})` is not quoting the prompt: "
            f"{shape!r} does not appear in adversary.md")
        bare = {k: "clear: holds here" for k in adversary.CRITERIA_KEYS}
        bare[n] = "clear"
        v, err = adversary.parse_verdict(json.dumps({"criteria": bare}))
        assert v is None
        assert shape in err, (
            f"the refusal on criterion {n} must show the rubric's own "
            f"way out; got {err!r}")


def test_the_refusal_follows_the_rubric_when_it_is_reworded(
        monkeypatch) -> None:
    """The one that proves DERIVATION rather than coincidence: reword
    the template and the way out must reword with it. A literal passes
    the test above on the day it is written and fails every reader
    afterwards. Each naming criterion is reworded on its own, so a
    refusal that quotes SOME naming entry rather than the one it is
    refusing does not pass."""
    import json
    for n in sorted(_naming_rules()):
        marker = f"clear: <the reworded naming for criterion {n}>"
        reworded = TEXT.replace(_template_naming_entry(n), marker)
        monkeypatch.setattr(adversary, "_prompt_text",
                            lambda text=reworded: text)
        bare = {k: "clear: holds here" for k in adversary.CRITERIA_KEYS}
        bare[n] = "clear"
        _v, err = adversary.parse_verdict(json.dumps({"criteria": bare}))
        assert marker in err, (
            f"the refusal on criterion {n} ignored the rubric it is "
            f"supposed to quote: {err!r}")


def test_the_parser_actually_refuses_a_bare_clear_there() -> None:
    """Behavioural, so the constant cannot drift away from the code that
    reads it — on every criterion the constant lists."""
    import json
    for n in adversary.NAMING_CRITERIA:
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
    never patch over a fired criterion.

    v6 (d5916446) trims the boundary to one clause and puts the escape
    hatch back as a worked case instead of a rider: "A PAST line
    without its citation is criterion 3." That pointer is checked
    against the criterion that actually demands citations, so the next
    renumber cannot leave the boundary directing a real defect at
    nothing."""
    assert ("Format defects and redundant Programme content do not "
            "rebut — keep them in reservations") in TEXT
    assert "a reservation must not be used to patch over one" in TEXT
    assert "A defect you can name belongs on its criterion's line" \
        not in TEXT, "the superseded sentence is still there, contradicting"
    m = re.search(r"A PAST line without its citation is criterion (\d)",
                  TEXT)
    assert m, ("the boundary no longer says which defects it does NOT "
               "send to reservations — a rule that forbids without "
               "naming the way out is the gate an agent cannot obey")
    assert m.group(1) == _citation_criterion(), (
        f"the boundary sends a missing citation to criterion "
        f"{m.group(1)}, but criterion {_citation_criterion()} is the "
        f"one whose line demands citations")


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
    wording; the honesty criterion carries the proof-not-conjecture
    standard now, so that half is read off the criterion that demands
    citations rather than off a quoted sentence (v6 rewrote it as
    "Conjecture treated as fact … is not allowed")."""
    route = _route_criterion()
    line = _criterion_line(route)
    assert "record" in line and "not allowed" in line, (
        "the route criterion no longer refuses a route the record has "
        f"already settled:\n{line}")
    assert route in adversary.NAMING_CRITERIA, (
        f"the route is judged by criterion {route}, which no longer "
        f"carries a naming obligation — the judge can clear the route "
        f"without saying where it goes")
    honesty = _criterion_line(_citation_criterion())
    assert "conjecture" in honesty.lower(), (
        "nothing holds a mathematical claim to a complete argument "
        f"rather than conjecture:\n{honesty}")


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
    catching, and that is what this has to catch.

    v6 (d5916446) rewrote all three at once (items beyond the wall, an
    unargued Relation, a route that contradicts the record or re-walks
    it in the same shape) and made the closing verb plural, which is
    why the sentence's shape is matched rather than quoted. The
    record refusal is pinned as one of the LISTED items: a rubric that
    only mentions the record somewhere in the line has stopped
    disallowing a route that runs against it."""
    line = _criterion_line(_route_criterion())
    refusal = line.rsplit(". ", 1)[-1]
    assert re.search(r"\b(is|are) not allowed\.$", refusal.rstrip()), (
        f"the route criterion no longer closes with a refusal:\n{line}")
    items = [p for p in refusal.split(", ")
             if p.strip() and not re.match(r"(is|are) not allowed", p)]
    assert len(items) >= 3, (
        f"the route clause is down to {len(items)} refusal(s); it has "
        f"listed three since 2026-08-13:\n{refusal}")
    assert any(p.startswith("or ") for p in items), refusal
    assert any("record" in p for p in items), (
        f"a route against the record is no longer one of the refused "
        f"items:\n{refusal}")


def test_every_criterion_refuses_a_bare_clear() -> None:
    """2026-08-29 (calibration survey): the reason requirement went
    five-wide — 70-94% of clears on the unforced criteria were the bare
    word, and the survey's rule-position experiment proved reasons
    appear only where the parser demands them. Refusal must name the
    criterion and show the way out."""
    import json
    for k in adversary.CRITERIA_KEYS:
        crit = {c: "clear: holds here" for c in adversary.CRITERIA_KEYS}
        for n in adversary.NAMING_CRITERIA:
            crit[n] = "clear: entry — distance"
        crit[k] = "clear"
        v, err = adversary.parse_verdict(json.dumps({"criteria": crit}))
        assert v is None, f"bare clear on {k} must be refused"
        assert f"criterion {k}" in err and "clear:" in err
