"""A fact may have one home. The read side is bound too.

The registry pattern (`state/failures.py`, `llm/capabilities.py`,
`core/config.CONFIG_SPEC`) already works, and it already had teeth on
the WRITE side: `test_failure_registry.py` AST-scans for
`failure_reason="…"` literals that name no registered reason. The read
side was on the honour system, and honour is exactly what fails at the
frequency reads happen: adding a table is rare and reviewed, adding a
consumer is constant and invisible.

2026-08-13 paid for that asymmetry. The worker-exception path in
`dispatcher.run` hand-listed its two cooling reasons while the
normal-result path a few hundred lines above read
`failures.TARGET_COOLDOWN_REASONS`. It stayed correct only while the
classifier returned exactly those two reasons — a coincidence, not an
invariant — and teaching the classifier a third would have left the new
one with no cooldown at all.

So: a literal collection of strings that lands entirely inside a
declared table's keys is a second copy of that table, and this test
refuses it. `docs/internal/STATUS.md` rule 12 already said so in prose,
and prose was violated twice after being written; this is the version
that cannot be forgotten.

WHAT THIS DELIBERATELY DOES NOT DO. It only sees literals. Build the
same list through a variable and it passes. That is not a hole worth
closing: the failure mode it targets is the LAZY path — someone typing
the two strings they happen to care about — which is the path every one
of the incidents actually took. A deliberate evasion is not the threat
model on a solo repo.

TWO MATCH MODES. Trait registries (`failures.REGISTRY`,
`capabilities.CAPABILITIES`) use SUBSET matching: any literal drawn
wholly from their keys is a hand-rolled predicate that should be a
trait. State vocabularies (`transitions.*`, `db.BATCH_DECISION_KINDS`)
use EXACT matching instead: a proper subset of a state vocabulary is
usually a legitimate bespoke predicate (43 of them measured across
Tooling/ on 2026-08-13 — "hard-terminals minus proved" and kin), so
subset mode would criminalize working code; a literal EQUAL to the
whole table is the signature of a copy (9 of 9 measured hits were
true copies, since converted). The exact tables carry no grandfather
list on purpose: an allowlisted exact copy that later drifts becomes a
proper subset and silently leaves the lint's sight, which is precisely
the failure the lint exists to catch. Repeated proper subsets across
modules deserve a DECLARED derived view (`GOAL_FAILED_TERMINALS` was
minted for exactly that), which then joins the exact tables here.

`WAKE_LEGALITY` is deliberately not a table of its own: its key set is
pinned to `PROBLEM_STATES` by design, so a copy of one is a copy of
the other, and `PROBLEM_STATES` is the named vocabulary.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from Tooling.llm import capabilities
from Tooling.state import db as _db
from Tooling.state import failures, transitions

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / "Tooling"


class _Table:
    """A declared vocabulary, its home, what a consumer should do
    instead of copying it, and how a copy is recognized (`match`:
    "subset" for trait registries, "exact" for state vocabularies)."""

    def __init__(self, name: str, keys: "set[str]", home: "set[str]",
                 instead: str, match: str = "subset") -> None:
        assert match in ("subset", "exact")
        self.name, self.keys, self.home, self.instead, self.match = (
            name, keys, home, instead, match)


def _tables() -> "list[_Table]":
    return [
        _Table(
            "failures.REGISTRY", set(failures.REGISTRY),
            {"Tooling/state/failures.py"},
            "ask the value: `failures.REGISTRY[reason].<trait>` (or a "
            "derived view like TARGET_COOLDOWN_REASONS). If the "
            "predicate you need has no trait yet, ADD THE TRAIT — that "
            "is the whole point, the reason then carries its own answer "
            "and no consumer has a list to keep in sync",
        ),
        _Table(
            "capabilities.CAPABILITIES", set(capabilities.CAPABILITIES),
            {"Tooling/llm/capabilities.py"},
            "ask the declaration: `capabilities.capabilities_for(name)."
            "<field>`. A list of provider NAMES is the name-keyed "
            "special case `capabilities.py` was written to abolish",
        ),
    ] + [
        _Table(
            f"transitions.{attr}", set(getattr(transitions, attr)),
            {"Tooling/state/transitions.py"},
            f"use `transitions.{attr}` — the whole set spelled out by "
            f"hand is a copy that goes quietly stale the day the "
            f"vocabulary gains a member; a DIFFERENT set you actually "
            f"mean is a bespoke predicate and passes untouched",
            match="exact",
        )
        for attr in (
            "GOAL_STATES", "GOAL_TERMINALS", "GOAL_HARD_TERMINALS",
            "GOAL_FAILED_TERMINALS", "STRATEGY_STATES",
            "STRATEGY_TERMINALS", "PROBLEM_STATES",
            "PROVED_RECEIPT_KINDS",
        )
    ] + [
        _Table(
            "db.BATCH_DECISION_KINDS", set(_db.BATCH_DECISION_KINDS),
            {"Tooling/state/db.py"},
            "use `db.BATCH_DECISION_KINDS` (its docstring exists to stop "
            "a future kind landing in two consumers and being forgotten "
            "in the third — which is what a literal copy guarantees)",
            match="exact",
        ),
    ]


#: Sites that predate the lint. Each says what it would become — an
#: allowlist without a plan is just a slower silence.
#:
#: Keyed by (posix path, sorted values) rather than line number so the
#: entry survives edits above it but NOT a change to the list itself.
_GRANDFATHERED: "dict[tuple[str, tuple[str, ...]], str]" = {
    ("Tooling/agent/phase2_context.py",
     ("agent_declined", "circular_decomposition", "no_progress",
      "parent_needs_fix")):
        "which declines get surfaced in the phase-2 context → trait "
        "`surfaced_in_context`",
    ("Tooling/pipeline/_retry.py",
     ("agent_declined", "agent_infeasible", "agent_shelved",
      "parent_needs_fix")):
        "which reasons carry a Strategist directive → trait "
        "`carries_directive`",
    ("Tooling/state/kb_ingest.py",
     ("agent_infeasible", "agent_shelved", "parent_needs_fix")):
        "which declines feed the KB → trait `feeds_kb`",
    ("Tooling/state/kb_ingest.py",
     ("agent_stuck_thinking", "strategist_noop")):
        "the non-decline half of the same KB predicate — same trait",
    ("Tooling/state/programme.py",
     ("agent_no_output", "agent_timeout", "daemon_shutdown",
      "framework_verify_error", "gateway_unreachable", "missing_dep",
      "provider_misconfigured", "quota_exhausted", "spawn_fast_fail",
      "system_killed", "transient_timeout", "unclassified_spawn_failure",
      "verify_infra")):
        "channels whose discard is a MACHINE failure → trait "
        "`infra_discard`. Already half-guarded by an invariant test "
        "asserting every provider_infra reason lands here, which is "
        "evidence the relation is real and belongs in the table",
    ("Tooling/llm/stream_parser.py", ("claude", "codex")):
        "which providers have a stream dialect → derive from "
        "`capabilities.stream_events`",
}


def _literal_string_groups(path: Path):
    """(lineno, sorted values) for every all-string tuple/list/set
    literal with at least two elements."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            continue
        vals = [e.value for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if len(vals) < 2 or len(vals) != len(node.elts):
            continue
        yield node.lineno, tuple(sorted(vals))


def _violations() -> "list[tuple[str, int, tuple[str, ...], _Table]]":
    found = []
    for table in _tables():
        for path in sorted(TOOLING.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel in table.home:
                continue
            for lineno, vals in _literal_string_groups(path):
                if table.match == "exact":
                    hit = set(vals) == table.keys
                else:
                    hit = all(v in table.keys for v in vals)
                if hit:
                    found.append((rel, lineno, vals, table))
    return found


def test_no_module_keeps_a_private_copy_of_a_declared_table() -> None:
    fresh = [(rel, ln, vals, t) for rel, ln, vals, t in _violations()
             if (rel, vals) not in _GRANDFATHERED]
    assert not fresh, (
        "a literal list of strings that lands entirely inside a declared "
        "table is a second copy of that table, and the copy is what goes "
        "stale:\n" + "\n".join(
            f"  {rel}:{ln}\n"
            f"    copies {t.name}: {list(vals)}\n"
            f"    instead — {t.instead}"
            for rel, ln, vals, t in fresh))


def test_the_grandfather_list_cannot_outlive_its_sites() -> None:
    """An allowlist that keeps entries after the code is fixed becomes
    permanent cover, which is this test's own version of "the marker
    table still exists but no longer matches". Fix a site, delete its
    entry — and this fails until you do."""
    live = {(rel, vals) for rel, _ln, vals, _t in _violations()}
    stale = sorted(key for key in _GRANDFATHERED if key not in live)
    assert not stale, (
        "these grandfathered sites no longer exist (fixed, moved, or "
        "reworded) — delete the entry so the list keeps meaning what it "
        "says:\n" + "\n".join(f"  {rel}: {list(vals)}" for rel, vals in stale))


@pytest.mark.parametrize("table", _tables(), ids=lambda t: t.name)
def test_every_table_says_what_to_do_instead(table: _Table) -> None:
    """The lint's message has to name an action the reader can take —
    the operator rule about gates applies to gates aimed at us too."""
    assert len(table.instead) > 40
    assert table.keys, f"{table.name} is empty — did the schema move?"
