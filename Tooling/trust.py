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

def print_axioms(theorem_name: str, cwd: str,
                 module_path: str | None = None) -> list[str]:
    """Return the axiom names that *theorem_name* depends on.

    P6.x patch 6 (Round-2 演習):
      - When *module_path* is provided (e.g.
        `Problems.smoke_p6.Goals.«1_reverse_length».reverse_length`), we
        first run `lake build <module_path>` to ensure the .olean exists,
        then write a tempfile with `import <module_path>` + `#print
        axioms <module_path>.<theorem_name>` and run lean on it. This is
        the path used by the production scheduler hook.
      - When *module_path* is None (legacy callers / unit tests), fall
        back to the bare `lean -e '#print axioms <theorem_name>'`
        invocation, which only works if the theorem is in the current
        toolchain's prelude or test framework provided PRINT_AXIOMS_MOCK.

    Test hook (mutually exclusive — see docs/dev/test_hooks.md):
      PRINT_AXIOMS_MOCK=none        → return [] (trivial / no axioms)
      PRINT_AXIOMS_MOCK=a,b,c      → return ['a', 'b', 'c']
    """
    mock = os.environ.get(_MOCK_ENV)
    if mock is not None:
        if mock.strip() == "none":
            return []
        return [a.strip() for a in mock.split(",") if a.strip()]

    if module_path is not None:
        # P6.x patch 23-fix-fix: `lake build <specific.module>` IS required
        # so the .olean materializes to disk for the tempfile's `import`
        # to resolve. (`lake env lean <file>` compiles in-process but
        # does not write the .olean — subsequent imports fail with
        # "object file ... does not exist".) Targeting a specific module
        # path triggers only that target's transitive imports — sibling
        # broken strategy files in the same directory glob are NOT
        # pulled in unless they're explicitly imported. Stale dead-
        # strategy files get cleaned up by _mark_strategy_dead so the
        # directory only contains live strategies + the goal file.
        try:
            build = subprocess.run(
                ["lake", "build", module_path],
                cwd=cwd, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"lake build {module_path!r} timed out after {_TIMEOUT}s"
            )
        if build.returncode != 0:
            raise RuntimeError(
                f"lake build {module_path!r} exit {build.returncode}: "
                f"stderr={(build.stderr or build.stdout)[:500].strip()!r}"
            )

        # Strategy file (patch 22) declares `theorem <slug>` under
        # namespace == module_path (file path), so theorem fully-
        # qualified name = module_path + "." + theorem_name (= slug).
        import tempfile
        full_name = f"{module_path}.{theorem_name}"
        body = (
            f"import {module_path}\n"
            f"#print axioms {full_name}\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".lean", delete=False, encoding="utf-8",
        ) as f:
            f.write(body)
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["lake", "env", "lean", tmp_path],
                cwd=cwd, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=_TIMEOUT,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if result.returncode != 0:
            raise RuntimeError(
                f"print_axioms({full_name!r}) exit {result.returncode}: "
                f"stderr={(result.stderr or result.stdout)[:500].strip()!r}"
            )
        return _parse_print_axioms_output(result.stdout)

    # Legacy bare-name path (unit tests / mock environments).
    cmd = ["lake", "env", "lean", "-e", f"#print axioms {theorem_name}"]
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
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
