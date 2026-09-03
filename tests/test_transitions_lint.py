"""Structural lint: goal/strategy STATUS mutations must go through the checked
mutators (`state.transitions` edge-checked apply_* → `db.update_goal_status` /
`db.update_strategy_status`), never via raw SQL UPDATE.

Companion of test_proof_store_lint.py — the same "chokepoint guarded by lint,
not code review" move, applied to the state-machine door (#11 unification).
Until this test existed the door was held shut by review discipline alone; the
known bypasses below are all deliberate and documented, but nothing stopped a
NEW one from slipping in.

Mechanism: per-file COUNT ratchet (not a blanket file whitelist). Every raw
`UPDATE goals|strategies SET … status =` in Tooling/ is counted; each file must
match its pinned count exactly.
  - count above the pin → a new raw status UPDATE appeared: route it through
    the checked mutator, or (for a migration backfill / deliberate bulk repair)
    bump the pin HERE with a justification line.
  - count below the pin → a bypass was removed: lower the pin so the ratchet
    stays tight (stale-pin prevention, same both-directions idea as the
    enum↔schema SoT tests).

Known limitation: table-name-interpolated SQL (f"UPDATE {t} SET status…")
escapes the regex — none exists today; don't introduce one.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_TOOLING = _REPO / "Tooling"

# `status =` within a short window of `UPDATE goals|strategies SET` — catches
# both single-line and wrapped/triple-quoted SQL without matching unrelated
# UPDATEs (queue/pipelines/library_decls or non-status column sets). The
# window is WHERE-tempered so a `status =` in the WHERE clause of a non-
# status SET (db.py's integrity_verified backfill filters on
# `status = 'proved'`) doesn't count as a status mutation.
_RAW_STATUS_UPDATE_RE = re.compile(
    r"UPDATE\s+(goals|strategies)\s+SET"
    r"(?:(?!\bWHERE\b)[\s\S]){0,160}?\bstatus\s*=",
    re.IGNORECASE)

# posix path relative to Tooling/ → pinned count of allowed raw status UPDATEs.
_ALLOWED: dict[str, int] = {
    # The official mutators themselves. update_goal_status (2 branches:
    # proved keeps integrity_verified, non-proved clears it) and
    # update_strategy_status (1) split from db.py into db/goals.py and
    # db/strategies.py respectively (2026-08-29 db.py package split).
    "state/db/goals.py": 2,
    "state/db/strategies.py": 1,
    # The disproved / bootstrap-frozen migration backfills (migrations run
    # at vocabulary-change points — the state machine's edges don't apply
    # to them). Split out of db.py 2026-07-07 (v24 schema rework).
    # 2→3 (v51, 2026-09-04): the `dead` → `shelved` rewrite. It is a
    # RENAME of a retired status, not a transition — no edge exists for
    # it (that is the point), and the migration writes the matching
    # `goal_events` rows itself.
    "state/db_migrations.py": 3,
    # Startup bulk repair (half-baked strategies → dead). Deliberately raw:
    # a bulk UPDATE skips update_strategy_status's inject-outcome hook,
    # compensated by null_inject_redispatch_specs — see the comment at the
    # call site. The two goal resync passes moved to the checked mutator
    # per-row 2026-08-18 (frankl_core anchor un-park: the bulk form wrote
    # no goal_events and knew nothing about delegate anchors).
    "state/recovery.py": 1,
    # Operator soft-reset CLI (attempts + status in one statement).
    # `core/cli.py` split move-only into `core/cli/` (task A3, 2026-08-28);
    # `_soft_reset` (the raw UPDATE's owner) landed in `problems.py`.
    "core/cli/problems.py": 1,
}


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def test_no_unpinned_raw_status_updates() -> None:
    actual: dict[str, list[int]] = {}
    for py in sorted(_TOOLING.rglob("*.py")):
        rel = py.relative_to(_TOOLING).as_posix()
        text = py.read_text(encoding="utf-8", errors="replace")
        lines = [_line_of(text, m.start())
                 for m in _RAW_STATUS_UPDATE_RE.finditer(text)]
        if lines:
            actual[rel] = lines

    problems: list[str] = []
    for rel, lines in actual.items():
        pin = _ALLOWED.get(rel, 0)
        if len(lines) > pin:
            problems.append(
                f"{rel}: {len(lines)} raw status UPDATE(s), pin is {pin} — "
                f"lines {lines}. Route the new one through "
                "transitions/db.update_*_status, or bump the pin with a "
                "justification.")
    for rel, pin in _ALLOWED.items():
        n = len(actual.get(rel, []))
        if n < pin:
            problems.append(
                f"{rel}: pin says {pin} but only {n} found — a bypass was "
                "removed; lower the pin so the ratchet stays tight.")
    assert not problems, "\n".join(problems)
