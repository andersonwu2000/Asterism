"""Cross-Problem axiom-coverage check (P6 C42).

Spec phase6_library.md ## In line 37-44 字面: 「Problem A 證出 lemma
用了 axiom set S_A、Problem B import 該 lemma 時，B 的 axioms 必須
⊇ S_A 內 mathematical 層 axiom」+ 「P6 採 CLI 手動觸發:
`asterism library check-deps` 包裝呼叫 `tools/check_axiom_coverage.lean`」.

C42 first cut: Python-side conservative coverage analysis that
walks library_index entries + reads each entry's source goal's
trust_set + checks against every Problem's META.md axioms. Reports
(consumer_problem, library_entry, missing_axioms) tuples for any
violations.

Strict version (the `tools/check_axiom_coverage.lean` Lean exe) is a
stub in C42 — real Lean exe walks each Library entry, runs
`#print axioms <name>`, and compares against per-Problem axioms.
Real Lean impl deferred to C44+ when CLI binding lands; until then
the Python wrapper here is the operator-facing tool.

Spec line 39 字面 「reviewer 不要寫 lake plugin」 — C42 hard rule:
no lake build hook. The check runs purely via SQL + META.md parse.

Public API:
    check_axiom_coverage(conn, base_dir) -> CheckDepsResult
        Walks library_index + cross-references with Problem.axioms.
        Returns CheckDepsResult with .violations + .skipped_problems.

    Violation dataclass — (consumer_problem, entry_name, axioms_used,
                            consumer_axioms, missing).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from Tooling.meta import scan_all_problems


@dataclass
class Violation:
    """One axiom-coverage violation: a Problem whose META.md axioms do
    not cover what a Library entry's trust_set requires."""
    consumer_problem: str
    entry_name: str               # library_index.name (e.g. 'list_lemmas.append_nil')
    axioms_used: frozenset[str]   # from entry's source goal trust_set
    consumer_axioms: frozenset[str]
    missing: frozenset[str]


@dataclass
class CheckDepsResult:
    """Outcome of one check_axiom_coverage run."""
    violations: list[Violation] = field(default_factory=list)
    skipped_problems: list[str] = field(default_factory=list)
    entries_checked: int = 0
    n_problems: int = 0


def _trust_set_axioms(trust_set_raw: Any) -> frozenset[str]:
    """Extract lean_axiom names from a goals.trust_set JSON column.

    spec line 38: "axioms 必須 ⊇ S_A 內 **mathematical 層 axiom**" —
    we filter `kind='lean_axiom'` since computational entries do not
    impose axiom-coverage requirements on consumers (they're concrete
    reproducible artifacts, not foundational dependencies).
    """
    if trust_set_raw is None:
        return frozenset()
    try:
        ts = (
            json.loads(trust_set_raw)
            if isinstance(trust_set_raw, str)
            else trust_set_raw
        )
    except json.JSONDecodeError:
        return frozenset()
    if not isinstance(ts, list):
        return frozenset()
    out: set[str] = set()
    for entry in ts:
        if isinstance(entry, dict) and entry.get("kind") == "lean_axiom":
            n = entry.get("name")
            if n:
                out.add(str(n))
    return frozenset(out)


def check_axiom_coverage(
    conn: sqlite3.Connection,
    base_dir: str | Path,
) -> CheckDepsResult:
    """Walk library_index ⊗ Problems, report axiom-coverage violations.

    For each Library entry we look up its source goal's trust_set,
    extract `kind='lean_axiom'` names, and verify every Problem's
    declared axioms ⊇ that set. Any Problem whose axioms miss at
    least one required axiom is reported as a Violation row.

    Conservative shape (C42 first cut):
      - We do NOT track which Problem actually imports which entry
        (`--imports` flag lands in C44). Without that, we report any
        Problem whose axioms cannot cover any entry — operator
        applies judgment to which violations are real.
      - We DO skip computational entries (covered by spec line 38
        「mathematical 層 axiom」字面).

    Returns CheckDepsResult.
    """
    result = CheckDepsResult()

    problems = scan_all_problems(base_dir)
    result.n_problems = len(problems)
    # Skipped problems = directories under Problems/ with bad META.md.
    base = Path(base_dir) / "Problems"
    if base.exists():
        for entry in sorted(base.iterdir()):
            if entry.is_dir() and entry.name not in problems:
                result.skipped_problems.append(entry.name)

    rows = conn.execute(
        "SELECT li.name, g.trust_set "
        "FROM library_index li "
        "LEFT JOIN goals g ON g.id = li.source_root_id "
        "WHERE li.layer = 'Theorems'"
    ).fetchall()
    result.entries_checked = len(rows)

    for entry_name, trust_set_raw in rows:
        used = _trust_set_axioms(trust_set_raw)
        if not used:
            # No mathematical axioms claimed by this entry — coverage
            # check is trivially satisfied.
            continue
        for prob_name, prob_meta in problems.items():
            consumer_axioms = prob_meta.axioms
            missing = used - consumer_axioms
            if missing:
                result.violations.append(Violation(
                    consumer_problem=prob_name,
                    entry_name=entry_name,
                    axioms_used=used,
                    consumer_axioms=consumer_axioms,
                    missing=missing,
                ))
    return result
