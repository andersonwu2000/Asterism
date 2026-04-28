"""Validator stage for the Backward pipeline (P2).

Three checks in order:
  1. max_subgoals  — proposed sub-Goal count <= MAX_SUBGOALS (config)
  2. slug_unique   — no proposed slug already in goals table
                      (runtime SELECT; schema_v1 has no (problem, slug) UNIQUE
                       constraint and P2 cannot extend schema)
  3. hyp_carry     — each sub-Goal carries all parent ∀-binders
                     (delegated to tools/validator.lean via subprocess;
                      Lean.Meta side does the actual binder extraction —
                      regex-parsing Lean source is forbidden by
                      architecture.md §7.4 / impl §4.1)

Public API:
  validate(conn, problem, parent_lean_path, subgoals, lake_cwd) -> list[ValidatorError]
  ValidatorError(check, detail)

impl §4.2 / phase2_decomposition.md §Scope In Validator.
"""
from __future__ import annotations

import json
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
# Check 3: hypothesis carry (delegated to tools/validator.lean)
# ---------------------------------------------------------------------------

def _parse_validator_json(stdout: str) -> dict | None:
    """Locate and parse validator.lean's JSON object output.

    Returns None if no parseable `{...}` line is found in *stdout*.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def check_hyp_carry(
    parent_lean_path: str,
    subgoals: list[dict[str, Any]],
    lake_cwd: str,
    timeout: float = 60.0,
) -> list[ValidatorError]:
    """Invoke tools/validator.lean and translate its JSON into ValidatorErrors.

    Each *subgoals* entry must have keys: 'id', 'lean_path'.
    *lake_cwd* must be a directory with a usable lake environment
    (e.g. D:/Hadamard for the Mathlib-backed cache).
    """
    # P6.x patch (Round-2 演習): drop the `--` separator. lake/lean v4.30
    # forwards `--` into argv and parseArgs rejects.
    cmd = [
        "lake", "env", "lean",
        "--run", str(_VALIDATOR_LEAN),
        "hypothesis_carry",
        "--parent", str(parent_lean_path),
        "--subgoals", *[str(sg["lean_path"]) for sg in subgoals],
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=lake_cwd,
            capture_output=True,
            text=True,

            encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [ValidatorError(check="hyp_carry", detail="validator.lean timed out")]

    parsed = _parse_validator_json(result.stdout)

    # No JSON line found anywhere — opaque failure (audit C11.R2 #4).
    if parsed is None:
        return [ValidatorError(
            check="hyp_carry",
            detail=(
                f"validator.lean produced no JSON output "
                f"(rc={result.returncode}); "
                f"stderr={result.stderr.strip()[:300]!r}"
            ),
        )]

    # Parent failed to elaborate — JSON is well-formed but flags it.
    if parsed.get("parent_error"):
        return [ValidatorError(
            check="hyp_carry",
            detail=f"parent elab failed: {parsed['parent_error']}",
        )]

    # Non-zero exit without parent_error: argv / runtime issue.
    if result.returncode != 0:
        return [ValidatorError(
            check="hyp_carry",
            detail=(
                f"validator.lean exited rc={result.returncode}; "
                f"stderr={result.stderr.strip()[:300]!r}"
            ),
        )]

    # Translate per-subgoal results back to caller-supplied IDs.
    path_to_id = {str(sg["lean_path"]): sg["id"] for sg in subgoals}

    errors: list[ValidatorError] = []
    for item in parsed.get("subgoals", []):
        path = item.get("subgoal", "")
        sg_id = path_to_id.get(path, path)
        if item.get("error"):
            errors.append(ValidatorError(
                check="hyp_carry",
                detail=f"sub-Goal '{sg_id}' elab failed: {item['error']}",
            ))
            continue
        missing = item.get("missing_binders", [])
        if missing:
            errors.append(ValidatorError(
                check="hyp_carry",
                detail=f"sub-Goal '{sg_id}' missing binders: {missing}",
            ))
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
    Order is cheap-to-expensive; max_subgoals is a hard gate.
    """
    err = check_max_subgoals(subgoals)
    if err:
        return [err]  # hard stop

    errors: list[ValidatorError] = []

    err = check_slug_unique(conn, problem, subgoals)
    if err:
        errors.append(err)

    errors.extend(check_hyp_carry(parent_lean_path, subgoals, lake_cwd))

    return errors
