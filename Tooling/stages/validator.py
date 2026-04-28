"""Validator stage for the Backward pipeline (P2).

Three checks in order:
  1. max_subgoals  — proposed sub-Goal count <= MAX_SUBGOALS (config)
  2. slug_unique   — no proposed slug already in goals table (SQL UNIQUE)
  3. hyp_carry     — each sub-Goal carries all parent binders (via tools/validator.lean)

Public API:
  validate(conn, problem, parent_lean_path, subgoals, lake_cwd) -> list[ValidatorError]
  ValidatorError(check, detail)

impl §4.2 / phase2_decomposition.md §Scope In Validator.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_SUBGOALS: int = 8  # validator.max_subgoals, phase2_decomposition.md §Config

_VALIDATOR_LEAN = Path(__file__).parents[2] / "tools" / "validator.lean"


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

@dataclass
class ValidatorError:
    check: str   # 'max_subgoals' | 'slug_unique' | 'hyp_carry'
    detail: str


# ---------------------------------------------------------------------------
# Type string extraction from .lean files
# ---------------------------------------------------------------------------

def _find_at_depth0(s: str, target: str, *, skip_assign: bool = True) -> int:
    """Return index of first *target* char in *s* at brace/paren depth 0.

    If *skip_assign* is True, a ':' immediately followed by '=' is skipped
    (so ':=' is not treated as a type separator).
    """
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and c == target:
            if skip_assign and target == ":" and i + 1 < len(s) and s[i + 1] == "=":
                i += 1  # skip ':='
            else:
                return i
        i += 1
    return -1


def extract_theorem_type(lean_content: str) -> str:
    """Extract the full ∀-type string from a theorem declaration in *lean_content*.

    For ``theorem foo (a : A) (b : B) : Q := ...``
      → ``∀ (a : A) (b : B), Q``

    For ``theorem foo : ∀ (a : A), Q := ...``
      → ``∀ (a : A), Q``

    Raises ValueError if no theorem declaration is found.
    """
    # Strip line comments so embedded '--' doesn't confuse parsing.
    lines = [re.sub(r"--.*", "", ln) for ln in lean_content.splitlines()]
    flat = " ".join(lines)

    # Find 'theorem <name>'
    m = re.search(r"\btheorem\s+\w[\w']*", flat)
    if m is None:
        raise ValueError("No 'theorem' declaration found in lean content")

    rest = flat[m.end():].lstrip()

    # Clip at ':=' position (depth-0)
    assign_pos = _find_at_depth0(rest, ":", skip_assign=False)
    # We want ':=' specifically
    def _find_define(s: str) -> int:
        depth = 0
        i = 0
        while i < len(s) - 1:
            c = s[i]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif depth == 0 and c == ":" and s[i + 1] == "=":
                return i
            i += 1
        return -1

    define_pos = _find_define(rest)
    sig = rest[:define_pos].strip() if define_pos != -1 else rest.strip()

    # Find the ':' separating explicit params from return type (depth-0, not ':=')
    colon_pos = _find_at_depth0(sig, ":", skip_assign=True)

    if colon_pos == -1:
        return sig.strip()

    params   = sig[:colon_pos].strip()
    ret_type = sig[colon_pos + 1:].strip()

    if params:
        return f"∀ {params}, {ret_type}"
    return ret_type


# ---------------------------------------------------------------------------
# Check 1: max_subgoals
# ---------------------------------------------------------------------------

def check_max_subgoals(subgoals: list[dict[str, Any]]) -> ValidatorError | None:
    if len(subgoals) > MAX_SUBGOALS:
        return ValidatorError(
            check="max_subgoals",
            detail=(
                f"{len(subgoals)} sub-Goals exceeds max_subgoals={MAX_SUBGOALS}"
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Check 2: slug uniqueness
# ---------------------------------------------------------------------------

def check_slug_unique(
    conn: sqlite3.Connection,
    problem: str,
    subgoals: list[dict[str, Any]],
) -> ValidatorError | None:
    """Return an error if any proposed slug already exists for *problem*."""
    for sg in subgoals:
        slug = sg["slug"]
        row = conn.execute(
            "SELECT id FROM goals WHERE problem = ? AND slug = ?",
            (problem, slug),
        ).fetchone()
        if row:
            return ValidatorError(
                check="slug_unique",
                detail=f"slug '{slug}' already exists in problem '{problem}'",
            )
    return None


# ---------------------------------------------------------------------------
# Check 3: hypothesis carry (via tools/validator.lean)
# ---------------------------------------------------------------------------

def _parse_lean_output(stdout: str) -> list[dict]:
    """Find the JSON array line in validator.lean stdout output."""
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("["):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return []


def check_hyp_carry(
    parent_lean_path: str,
    subgoals: list[dict[str, Any]],
    lake_cwd: str,
    timeout: float = 30.0,
) -> list[ValidatorError]:
    """Run tools/validator.lean to check hypothesis carry.

    Each entry in *subgoals* must have keys: 'id', 'lean_path'.
    *lake_cwd* is the directory with a lake environment (e.g. D:/Hadamard).
    """
    # Extract type strings
    parent_type = extract_theorem_type(
        Path(parent_lean_path).read_text(encoding="utf-8")
    )
    subgoals_input = []
    for sg in subgoals:
        type_str = extract_theorem_type(
            Path(sg["lean_path"]).read_text(encoding="utf-8")
        )
        subgoals_input.append({"id": sg["id"], "type_str": type_str})

    env = {
        **os.environ,
        "VALIDATOR_PARENT_TYPE": parent_type,
        "VALIDATOR_SUBGOALS": json.dumps(subgoals_input, ensure_ascii=False),
    }

    try:
        result = subprocess.run(
            ["lake", "env", "lean", str(_VALIDATOR_LEAN)],
            cwd=lake_cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [ValidatorError(check="hyp_carry", detail="validator.lean timed out")]

    lean_results = _parse_lean_output(result.stdout)

    errors: list[ValidatorError] = []
    for item in lean_results:
        missing = item.get("missing_binders", [])
        if missing:
            errors.append(
                ValidatorError(
                    check="hyp_carry",
                    detail=(
                        f"sub-Goal '{item['subgoal']}' missing binders: {missing}"
                    ),
                )
            )
        for mm in item.get("type_mismatches", []):
            errors.append(
                ValidatorError(
                    check="hyp_carry",
                    detail=(
                        f"sub-Goal '{item['subgoal']}' binder '{mm['name']}' "
                        f"type mismatch: parent={mm['parent_type']!r} "
                        f"subgoal={mm['subgoal_type']!r}"
                    ),
                )
            )
    return errors


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------

def validate(
    conn: sqlite3.Connection,
    problem: str,
    parent_lean_path: str,
    subgoals: list[dict[str, Any]],
    lake_cwd: str,
) -> list[ValidatorError]:
    """Run all validator checks.  Returns a (possibly empty) list of errors.

    *subgoals* is a list of dicts with keys: 'id', 'slug', 'lean_path'.
    Checks are run in order; max_subgoals is a hard gate (stops on fail).
    """
    errors: list[ValidatorError] = []

    err = check_max_subgoals(subgoals)
    if err:
        return [err]  # hard stop

    err = check_slug_unique(conn, problem, subgoals)
    if err:
        errors.append(err)

    errors.extend(
        check_hyp_carry(parent_lean_path, subgoals, lake_cwd)
    )

    return errors
