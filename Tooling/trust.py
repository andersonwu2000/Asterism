"""Trust set construction and accept rule (impl §5.2 + §5.3).

print_axioms(theorem_name, cwd) -> list[str]
    Run `lake env lean -e '#print axioms <theorem>'` and return axiom names.

build_trust_set(axioms) -> list[dict]
    Wrap each axiom name into a lean_axiom trust entry.

check_accept_rule(trust_set, allowed_axioms) -> tuple[bool, list[str]]
    Accept rule for status='proved' / type='classical':
    every entry must satisfy kind='lean_axiom' AND name ∈ allowed_axioms.
    Returns (accepted, rejected_names).
"""
from __future__ import annotations

import os
import re
import subprocess


_TIMEOUT: float = 60.0  # seconds (impl §5.2)
_MOCK_ENV = "PRINT_AXIOMS_MOCK"

# Lean 4 '#print axioms' outputs a bracketed list when axioms exist:
#   'Nat.mul_assoc' depends on axioms: [propext, Quot.sound]
# and plain text when none:
#   'Nat.add_comm' does not depend on any axioms
_BRACKET_RE = re.compile(r'\[([^\]]+)\]')


# ---------------------------------------------------------------------------
# print_axioms
# ---------------------------------------------------------------------------

def print_axioms(theorem_name: str, cwd: str) -> list[str]:
    """Return the axiom names that *theorem_name* depends on.

    Runs ``lake env lean -e '#print axioms <theorem_name>'`` from *cwd*.
    Raises RuntimeError on subprocess timeout.

    Test hook (mutually exclusive — see docs/dev/test_hooks.md):
      PRINT_AXIOMS_MOCK=none        → return [] (trivial / no axioms)
      PRINT_AXIOMS_MOCK=a,b,c      → return ['a', 'b', 'c']
    """
    mock = os.environ.get(_MOCK_ENV)
    if mock is not None:
        if mock.strip() == "none":
            return []
        return [a.strip() for a in mock.split(",") if a.strip()]

    cmd = ["lake", "env", "lean", "-e", f"#print axioms {theorem_name}"]
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"print_axioms timed out for '{theorem_name}' after {_TIMEOUT}s"
        )

    # Reject silent-failure path: lake build error / unknown identifier / toolchain
    # missing all surface as rc != 0.  Without this, an empty stdout would parse
    # to [] and check_accept_rule would vacuously accept the Goal as proved.
    if result.returncode != 0:
        raise RuntimeError(
            f"print_axioms('{theorem_name}') exit {result.returncode}: "
            f"stderr={result.stderr[:500].strip()!r}"
        )

    return _parse_print_axioms_output(result.stdout)


def _parse_print_axioms_output(output: str) -> list[str]:
    """Parse ``#print axioms`` stdout into an axiom name list.

    Lean 4 formats observed (spike-002):
      '<thm>' depends on axioms: [propext, Quot.sound, Classical.choice]
      '<thm>' does not depend on any axioms
    """
    m = _BRACKET_RE.search(output)
    if not m:
        return []
    content = m.group(1)
    return [a.strip() for a in content.split(",") if a.strip()]


# ---------------------------------------------------------------------------
# build_trust_set
# ---------------------------------------------------------------------------

def build_trust_set(axioms: list[str]) -> list[dict]:
    """Build a lean_axiom trust entry list from *axioms* (impl §5.2).

    Each entry shape (impl §5.1 JSON):
      {"name": ..., "kind": "lean_axiom", "provenance": "lean #print axioms"}
    confidence is omitted (implicitly 1.0 per spec).
    """
    return [
        {
            "name": name,
            "kind": "lean_axiom",
            "provenance": "lean #print axioms",
        }
        for name in axioms
    ]


# ---------------------------------------------------------------------------
# check_accept_rule
# ---------------------------------------------------------------------------

def check_accept_rule(
    trust_set: list[dict],
    allowed_axioms: set[str] | frozenset[str],
) -> tuple[bool, list[str]]:
    """Accept rule for status='proved' / answer_data.type='classical' (impl §5.3).

    Every entry in *trust_set* must satisfy:
      kind == 'lean_axiom'  AND  name ∈ allowed_axioms

    Returns (accepted: bool, rejected_names: list[str]).
    An empty trust_set is accepted (trivial proof with no axiom dependencies).
    """
    rejected: list[str] = []
    for entry in trust_set:
        name = entry.get("name", "<unknown>")
        if entry.get("kind") != "lean_axiom":
            rejected.append(name)
        elif name not in allowed_axioms:
            rejected.append(name)
    return (len(rejected) == 0, rejected)
