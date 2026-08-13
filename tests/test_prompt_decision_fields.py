"""A worked example must use the field name the parser actually reads.

`Inject` carries a PROOF — the part of the batch's `## Proof` that
settles this brick. `Delegate` carries a BRIEF — a charter, a claim a
new group must settle, which is not a proof of anything. `_parse_one`
names them apart on purpose, and its comment says why: sharing a row is
not sharing a meaning.

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

import pytest

from Tooling.pipeline import strategist

PROMPTS = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"

#: A JSON object literal in a fenced example, flat (no nesting) — which
#: is the shape every decision example in these prompts has.
_OBJ = re.compile(r'\{[^{}]*"kind":\s*"(\w+)"[^{}]*\}', re.S)


def _field_the_parser_reads(kind: str) -> str:
    """Feed `_parse_one` one payload per candidate field and see which
    one lands in `.brief`. Behavioural, so a future rename moves this
    test's expectation automatically instead of leaving it asserting
    yesterday's contract."""
    reads = []
    for field in ("proof", "brief"):
        d, _err = strategist._parse_one({"kind": kind, field: "X"})
        if d is not None and getattr(d, "brief", None) == "X":
            reads.append(field)
    assert len(reads) == 1, (
        f"{kind} reads {reads or 'nothing'} — this test assumes exactly "
        f"one prose field per decision kind")
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


@pytest.mark.parametrize("kind", ["Inject", "Delegate"])
def test_the_two_prose_fields_are_still_distinct(kind: str) -> None:
    """If these ever collapse onto one name the rest of this file is
    pointless, and the collapse itself would be the bug: an Inject's
    prose is an argument, a Delegate's is a charter."""
    assert _field_the_parser_reads("Inject") == "proof"
    assert _field_the_parser_reads("Delegate") == "brief"


def test_every_example_uses_the_field_its_kind_reads() -> None:
    wrong = []
    for f, ln, kind, block in _examples():
        try:
            want = _field_the_parser_reads(kind)
        except AssertionError:
            continue        # kinds with no prose field at all
        other = "brief" if want == "proof" else "proof"
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
_KWARG = re.compile(r"\b(brief|proof)\s*=")


def _call_shapes() -> "list[tuple[str, int, str, str]]":
    """(where, line, kind, field) for every call shape that names a
    prose field, across BOTH homes."""
    out = []
    files = list(PROMPTS.rglob("*.md")) + [
        p for p in CODE.rglob("*.py")
        # The operator's local zh-TW prompt drafts are not shipped and
        # are deliberately not committed; they are not a surface an
        # agent ever reads.
        if "prompts_zhtw_ref" not in p.parts]
    for f in sorted(files):
        s = f.read_text(encoding="utf-8", errors="replace")
        for m in _CALL.finditer(s):
            for kw in _KWARG.finditer(m.group(2)):
                out.append((str(f.relative_to(CODE.parent)),
                            s[:m.start()].count("\n") + 1,
                            m.group(1), kw.group(1)))
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
    outlived the rename in the first place."""
    wrong = []
    for where, ln, kind, field in _call_shapes():
        want = _field_the_parser_reads(kind)
        if field != want:
            wrong.append(f"  {where}:{ln} — {kind}({field}=…) but the "
                         f"parser reads {want!r}")
    assert not wrong, (
        "these tell the Strategist to write a field the parser will "
        "refuse; the ones inside rejection messages are worse than the "
        "prompts, because they fire when it is already in trouble:\n"
        + "\n".join(wrong))


def test_the_label_shown_back_follows_the_kind() -> None:
    """The third surface: what the framework CALLS a decision's prose
    when it echoes it back in Context. The DB column is `brief` for both
    kinds, and printing the column name taught `brief` for Injects on
    every wake. `_prose_label` is the one place that answers it."""
    from Tooling.agent.phase2_context import _prose_label
    assert _prose_label("Inject") == _field_the_parser_reads("Inject")
    assert _prose_label("Delegate") == _field_the_parser_reads("Delegate")
    # An unknown kind must not silently claim to be a proof.
    assert _prose_label(None) == "brief"


def test_delegate_has_no_worked_example_yet() -> None:
    """Recorded, not enforced. `Delegate` is the ONE kind whose prose
    field differs from `Inject`'s, and it is the one kind with no
    example to copy — which is how the confusion had room to start.

    Left as a failing-when-fixed marker rather than a silent gap: adding
    the example is a prompt-wording change, and those go past the owner
    before they ship. Delete this test in the same edit that adds one.
    """
    kinds = {k for _f, _ln, k, _b in _examples()}
    assert "Delegate" not in kinds, (
        "a Delegate example exists now — good; delete this test, its "
        "job is done")
