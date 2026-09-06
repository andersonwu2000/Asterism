"""A worked example must use the field name the parser actually reads.

`Inject` carries a BRICK NAME since 2026-09-07 — the `### <name>` of
the brick in the batch's `## Proof` that this decision dispatches; the
argument itself is never copied. `Delegate` carries a CHARTER, a claim
a new group must settle. `_parse_one` names them apart on purpose, and
its comment says why: sharing a row is not sharing a meaning. The
`proof` mapping survives ONLY so a decision that still carries one
lands where verify can refuse it by name.

The spec paragraphs said `proof`. Ten worked examples underneath them
said `brief`, and every one was a `"kind": "Inject"` — so a Strategist
that copied the example got its batch refused with "Inject requires
non-empty `proof`". Not a confusion cost: a rejected batch is a wake.

The examples were left behind by an intentional rename, which is the
ordinary way this happens — the spec is what you edit, the examples are
what the reader copies. So the pin below asks the PARSER what each kind
reads, and holds the examples to that answer, rather than comparing one
piece of prose against another.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from Tooling.pipeline import strategist
from Tooling.pipeline.strategist.model import brick_name_of

PROMPTS = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"

#: A JSON object literal in a fenced example, flat (no nesting) — which
#: is the shape every decision example in these prompts has.
_OBJ = re.compile(r'\{[^{}]*"kind":\s*"(\w+)"[^{}]*\}', re.S)

#: Every decision.json key that has ever carried a kind's OWN argument —
#: the retired ones included, because a guard that only knows the current
#: spelling goes blind exactly when a rename happens, which is the drift
#: this file exists to catch. Feeding all four costs nothing: the
#: derivation below asks the parser which one lands, and the answer moves
#: on its own.
_CANDIDATE_FIELDS = ("brick", "brief", "proof", "charter")

#: Candidate fields a kind may legally carry BESIDE the one it reads. A
#: Delegate's `brief` is the optional guidance hand-off (2026-08-19) —
#: real payload the child's context renders, so naming it is not drift.
_LEGAL_AUX: dict[str, frozenset[str]] = {"Delegate": frozenset({"brief"})}


def _reader(kind: str):
    """How the machine gets a kind's argument back out of a decision the
    parser produced.

    An `Inject`'s argument is a NAME, not prose — a structured param like
    `target_goal_id`, read out of `payload` by `brick_name_of`
    (2026-09-07 named bricks). Every other kind's argument is the one
    piece of prose a decision carries, and lands in the shared `brief`
    column."""
    if kind == "Inject":
        return brick_name_of
    return lambda d: getattr(d, "brief", None)


def _field_the_parser_reads(kind: str) -> str:
    """Feed `_parse_one` one payload per candidate field and see which
    one comes back out through this kind's reader. Behavioural, so a
    future rename moves this test's expectation automatically instead of
    leaving it asserting yesterday's contract."""
    reads = []
    for field in _CANDIDATE_FIELDS:
        d, _err = strategist._parse_one({"kind": kind, field: "X"})
        if d is not None and _reader(kind)(d) == "X":
            reads.append(field)
    assert len(reads) == 1, (
        f"{kind} reads {reads or 'nothing'} — this test assumes exactly "
        f"one argument field per decision kind")
    return reads[0]


def _examples() -> "list[tuple[Path, int, str, str]]":
    """(file, line, kind, block) for every decision example."""
    out = []
    for f in sorted(PROMPTS.rglob("*.md")):
        s = f.read_text(encoding="utf-8")
        for m in _OBJ.finditer(s):
            out.append((f, s[:m.start()].count("\n") + 1,
                        m.group(1), m.group(0)))
    return out


def test_there_are_examples_to_check() -> None:
    """A regex that silently matches nothing would make every assertion
    below vacuously true — the exact way a guard rots."""
    kinds = {k for _f, _ln, k, _b in _examples()}
    assert "Inject" in kinds, "no Inject examples found — did the fences move?"


def test_the_two_argument_fields_are_still_distinct() -> None:
    """If these ever collapse onto one name the rest of this file is
    pointless, and the collapse itself would be the bug: a Delegate's
    prose is a charter (2026-08-19: the wire key says so; `brief`
    became the optional guidance hand-off, parked in payload, never
    the judged prose), and an Inject's argument is the NAME of a brick
    in its batch's `## Proof` (2026-09-07) — it carries no prose at
    all."""
    assert _field_the_parser_reads("Inject") == "brick"
    assert _field_the_parser_reads("Delegate") == "charter"


def test_the_retired_proof_field_still_reaches_its_refusal() -> None:
    """`proof` is RETIRED for an Inject, and `brief_field` maps it
    anyway — on purpose. Drop that mapping and a decision.json that
    still carries a copied argument would be swallowed into `payload`
    and silently ignored; the mapping is what puts it in `.brief`,
    where `verify_decision` refuses it BY NAME ("Inject no longer
    carries `proof`: name the brick instead"). The route, not the
    contract."""
    d, _err = strategist._parse_one({"kind": "Inject", "proof": "X"})
    assert d is not None and d.brief == "X", (
        "a legacy `proof` no longer lands in `.brief` — verify's "
        "by-name refusal is now unreachable and the copied argument is "
        "silently dropped instead")


def test_every_example_uses_the_field_its_kind_reads() -> None:
    wrong = []
    for f, ln, kind, block in _examples():
        try:
            want = _field_the_parser_reads(kind)
        except AssertionError:
            continue        # kinds with no argument field at all
        # For a Delegate, `brief` is a LEGAL auxiliary key (the
        # guidance hand-off) — only a key that silently misreads as
        # the judged prose is wrong.
        legal_aux = _LEGAL_AUX.get(kind, frozenset())
        for other in set(_CANDIDATE_FIELDS) - {want} - legal_aux:
            if f'"{other}"' in block:
                wrong.append(f"  {f.name}:{ln} — {kind} example uses "
                             f'"{other}", but the parser reads "{want}"')
    assert not wrong, (
        "a worked example is teaching a field the parser will not read, "
        "so a Strategist that copies it gets the batch refused:\n"
        + "\n".join(wrong))


def test_the_examples_actually_parse(  # noqa: D401 — reads as a statement
) -> None:
    """Beyond the field name: an example that does not survive
    `_parse_one` is teaching a shape the machine rejects."""
    broken = []
    for f, ln, kind, block in _examples():
        try:
            obj = json.loads(block)
        except ValueError:
            continue        # elided/illustrative fragments, not payloads
        try:
            d, err = strategist._parse_one(obj)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"  {f.name}:{ln} {kind}: {type(exc).__name__}")
            continue
        if d is None:
            broken.append(f"  {f.name}:{ln} {kind}: {err}")
    assert not broken, "examples the parser cannot read:\n" + "\n".join(broken)


# ---------------------------------------------------------------------
# The OTHER home (2026-08-14)
# ---------------------------------------------------------------------
#
# The pin above walks `Tooling/prompts/*.md`. That is not where the
# Strategist reads most of its instructions when something has gone
# wrong: a rejection message, a stall gate, a Context section — all
# built in Python, all telling it what to write next, and none of them
# covered here. Eight of them still said `Inject(…, brief=…)` on
# 2026-08-14, three days after the rename, and the ones that matter
# most are the rejection messages: the agent is told how to fix its
# batch, does exactly that, and is refused again.
#
# So the same question gets asked of both homes.

CODE = Path(__file__).resolve().parents[1] / "Tooling"

#: `Inject(… field=…)` / `Delegate(… field=…)` written as a call shape,
#: in prose or in a message string. `[^)\n]*` keeps it to one line so a
#: stray paren later in a paragraph cannot swallow the rest of a file.
_CALL = re.compile(r"\b(Inject|Delegate)\(([^)\n]*)\)")
#: The keyword a call shape names its kind's argument with. It lists
#: every candidate — `Inject(brick=…)`, `Delegate(charter=…)`, and the
#: wrong ones this guard exists to catch, `proof=` above all. It read
#: `brief|proof` until 2026-09-07 and matched NOTHING once named bricks
#: landed and `243f1a92` took the last `proof=` out of Context: the
#: anti-vacuity test below is what said so, out loud, instead of letting
#: every assertion here pass on an empty list.
_KWARG = re.compile(rf"\b({'|'.join(_CANDIDATE_FIELDS)})\s*=")


def _call_shapes() -> "list[tuple[str, int, str, frozenset[str]]]":
    """(where, line, kind, fields) for every call shape that names at
    least one candidate field, across BOTH homes.

    Per SHAPE, not per keyword: `Delegate(charter=…, brief=…)` names its
    field and hands over guidance beside it, which is the contract, and a
    per-keyword reading would convict it for the second half."""
    out = []
    files = list(PROMPTS.rglob("*.md")) + list(CODE.rglob("*.py"))
    for f in sorted(files):
        s = f.read_text(encoding="utf-8", errors="replace")
        for m in _CALL.finditer(s):
            fields = frozenset(kw.group(1)
                               for kw in _KWARG.finditer(m.group(2)))
            if fields:
                out.append((str(f.relative_to(CODE.parent)),
                            s[:m.start()].count("\n") + 1,
                            m.group(1), fields))
    return out


def test_there_are_call_shapes_to_check() -> None:
    """Same anti-vacuity guard as above — and it has teeth twice over,
    because a regex that stops matching would hide the very drift this
    file exists for."""
    shapes = _call_shapes()
    assert shapes, "no call shapes found at all — did the phrasing move?"
    assert any(k == "Inject" for _w, _l, k, _f in shapes)


def test_every_call_shape_names_the_field_its_kind_reads() -> None:
    """Prose and generated messages, held to the parser's answer.

    A call shape is copied more literally than a spec paragraph is
    read — it looks like the thing you type — which is why the examples
    outlived the rename in the first place. Two ways to fail: naming a
    field the parser does not read for this kind (`proof=` anywhere is
    the retired one, and it is never legal for either kind), or naming
    only auxiliaries and never the field itself."""
    wrong = []
    for where, ln, kind, fields in _call_shapes():
        want = _field_the_parser_reads(kind)
        legal_aux = _LEGAL_AUX.get(kind, frozenset())
        for field in sorted(fields - {want} - legal_aux):
            retired = " (RETIRED 2026-09-07)" if field == "proof" else ""
            wrong.append(f"  {where}:{ln} — {kind}({field}=…){retired} "
                         f"but the parser reads {want!r}")
        if want not in fields:
            wrong.append(f"  {where}:{ln} — {kind}(…) names "
                         f"{sorted(fields)} but never {want!r}, the field "
                         f"the parser actually reads")
    assert not wrong, (
        "these tell the Strategist to write a field the parser will "
        "refuse; the ones inside rejection messages are worse than the "
        "prompts, because they fire when it is already in trouble:\n"
        + "\n".join(wrong))


def test_the_label_shown_back_follows_the_kind() -> None:
    """The third surface: what the framework CALLS a decision's prose
    when it echoes it back in Context. The DB column is `brief` for both
    kinds, and printing the column name taught `brief` for Injects on
    every wake. `_prose_label` is the one place that answers it.

    An Inject's label is `brick` since 2026-09-07 — the field it writes
    on the wire, which is also what the Context is showing back: the
    named brick, resolved out of `bricks`. Both kinds are pinned to the
    parser's own answer, so the label cannot outlive a rename the way
    the worked examples did.
    """
    from Tooling.agent.phase2_context import _prose_label
    assert _prose_label("Inject") == _field_the_parser_reads("Inject")
    assert _prose_label("Delegate") == _field_the_parser_reads("Delegate")
    # An unknown kind must not silently claim to be a proof.
    assert _prose_label(None) == "brief"
