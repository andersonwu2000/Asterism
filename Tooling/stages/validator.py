"""Validator stage for the Backward pipeline (P2; P6.x patch 29 batch mode).

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

Two hyp_carry transports:
  - check_hyp_carry        — legacy per-file; one runFrontend per .lean file
                              (Mathlib re-loaded N+1 times → 600s+ timeouts).
  - check_hyp_carry_batch  — P6.x patch 29; sends parent + subgoals as JSON,
                              validator.lean synthesizes a single combined
                              source, single runFrontend, Mathlib loads once.

`validate()` uses batch mode by default. Legacy mode kept exported for
backwards-compatible test fixtures that mock it directly.

Public API:
  validate(conn, problem, parent_lean_path, parent_statement,
           subgoals, lake_cwd) -> list[ValidatorError]
  ValidatorError(check, detail)

impl §4.2 / phase2_decomposition.md §Scope In Validator.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
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
    timeout: float = 600.0,  # P6.x patch 27: bump 300→600s.
                              # validator.lean uses enableInitializersExecution
                              # per call (patch 15) which triggers full Mathlib
                              # init even with .olean cache. Per-file
                              # runFrontend still 60-120s × N subgoals.
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
# Check 3 (batch): hypothesis carry via single-runFrontend synthesis
# ---------------------------------------------------------------------------

def check_hyp_carry_batch(
    problem: str,
    parent_slug: str,
    parent_statement: str,
    subgoals: list[dict[str, Any]],
    lake_cwd: str,
    timeout: float = 600.0,
    extra_imports: list[str] | None = None,
) -> list[ValidatorError]:
    """P6.x patch 29: batch hypothesis_carry.

    Sends one JSON input file describing parent + subgoals; validator.lean
    synthesizes a single combined source and runs runFrontend ONCE. Mathlib
    cold-load amortizes across all N subgoals (vs N+1 cold loads in legacy
    per-file mode).

    *subgoals* entries must have keys: 'id', 'slug', 'statement'. The 'id'
    is used only for ValidatorError attribution back to caller-supplied IDs.
    """
    payload = {
        "problem": problem,
        "parent": {"slug": parent_slug, "statement": parent_statement},
        "subgoals": [
            {"slug": sg["slug"], "statement": sg["statement"]}
            for sg in subgoals
        ],
        "imports": extra_imports or [],
    }

    # Write JSON to a temp file (passing as argv would explode for long Lean
    # type expressions and complicate quoting).
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8",
    ) as fp:
        json.dump(payload, fp)
        json_path = fp.name

    cmd = [
        "lake", "env", "lean",
        "--run", str(_VALIDATOR_LEAN),
        "hypothesis_carry_batch",
        "--json", json_path,
    ]

    try:
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
            return [ValidatorError(
                check="hyp_carry",
                detail=f"validator.lean (batch) timed out after {timeout}s",
            )]

        parsed = _parse_validator_json(result.stdout)
        if parsed is None:
            return [ValidatorError(
                check="hyp_carry",
                detail=(
                    f"validator.lean (batch) produced no JSON output "
                    f"(rc={result.returncode}); "
                    f"stderr={result.stderr.strip()[:300]!r}"
                ),
            )]

        if parsed.get("parent_error"):
            return [ValidatorError(
                check="hyp_carry",
                detail=f"batch elab failed: {parsed['parent_error']}",
            )]

        if result.returncode != 0:
            return [ValidatorError(
                check="hyp_carry",
                detail=(
                    f"validator.lean (batch) exited rc={result.returncode}; "
                    f"stderr={result.stderr.strip()[:300]!r}"
                ),
            )]

        # validator.lean batch reports per-subgoal by slug; map back to the
        # caller-supplied 'id' for the error message.
        slug_to_id = {sg["slug"]: sg.get("id", sg["slug"]) for sg in subgoals}

        errors: list[ValidatorError] = []
        for item in parsed.get("subgoals", []):
            slug = item.get("subgoal", "")
            sg_id = slug_to_id.get(slug, slug)
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
    finally:
        try:
            Path(json_path).unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------

def validate(
    conn: sqlite3.Connection,
    problem: str,
    parent_lean_path: str,
    subgoals: list[dict[str, Any]],
    lake_cwd: str,
    parent_slug: str | None = None,
    parent_statement: str | None = None,
) -> list[ValidatorError]:
    """Run all validator checks.  Returns a (possibly empty) list of errors.

    *subgoals* is a list of dicts with keys: 'id', 'slug', 'lean_path' and
    (when batch mode is used) 'statement'.

    P6.x patch 29: when *parent_slug* + *parent_statement* are provided,
    use batch hyp_carry (one runFrontend amortizing Mathlib load). When
    omitted, fall back to legacy per-file mode for backwards compat —
    callers without DB-side parent statement should migrate.
    """
    err = check_max_subgoals(subgoals)
    if err:
        return [err]  # hard stop

    errors: list[ValidatorError] = []

    err = check_slug_unique(conn, problem, subgoals)
    if err:
        errors.append(err)

    if parent_slug is not None and parent_statement is not None:
        # Batch mode requires each subgoal to have 'statement'.
        if any("statement" not in sg for sg in subgoals):
            errors.append(ValidatorError(
                check="hyp_carry",
                detail="batch mode requires each subgoal to have 'statement'",
            ))
        else:
            errors.extend(check_hyp_carry_batch(
                problem=problem,
                parent_slug=parent_slug,
                parent_statement=parent_statement,
                subgoals=subgoals,
                lake_cwd=lake_cwd,
            ))
    else:
        errors.extend(check_hyp_carry(parent_lean_path, subgoals, lake_cwd))

    return errors
