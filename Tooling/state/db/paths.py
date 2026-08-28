from __future__ import annotations

import sqlite3
from pathlib import Path


# ---------------------------------------------------------------------
# Problem name ↔ filesystem path mapping
# ---------------------------------------------------------------------
#
# A problem's "name" (= the `problem` column) is a dot-separated slug
# whose components map 1:1 to filesystem directory components under
# `Problems/`.
#
# Top-level problem (legacy / hand-authored):
#   slug:        "sylvester_gallai"
#   on disk:     Problems/sylvester_gallai/
#   Lean ns:     Problems.sylvester_gallai
#
# Nested problem (benchmark imports, multi-category collections):
#   slug:        "Minif2f.mathd_algebra_10"
#   on disk:     Problems/Minif2f/mathd_algebra_10/
#   Lean ns:     Problems.Minif2f.mathd_algebra_10
#
# The `.` separator is a deliberate choice — Lean namespace syntax
# uses `.` natively, so `f"Problems.{problem}.Root"`-style string
# concatenation in module path / namespace generation needs ZERO
# changes for nested support. Only filesystem accesses need to
# convert dots to path separators via `problem_dir()`.

def problem_dir(workspace: Path, problem: str) -> Path:
    """Map a problem slug to its filesystem directory.

    `problem` is the dot-separated slug as stored in the `problems` /
    `goals` `problem` columns. For legacy single-component slugs
    (`"sylvester_gallai"`) this returns `workspace/Problems/sylvester_gallai/`.
    For nested slugs (`"Minif2f.algebra_1"`) it returns
    `workspace/Problems/Minif2f/algebra_1/`.
    """
    return workspace / "Problems" / Path(*problem.split("."))


def slug_from_problem_dir(workspace: Path, pdir: Path) -> str:
    """Inverse of `problem_dir`. Given a problem's filesystem
    directory, return the dot-separated slug. Raises ValueError if
    `pdir` is not under `workspace/Problems/`.
    """
    rel = pdir.resolve().relative_to((workspace / "Problems").resolve())
    if not rel.parts:
        raise ValueError(f"{pdir} resolves to Problems/ root, not a problem dir")
    return ".".join(rel.parts)


def classify_cited_slug(
    conn: sqlite3.Connection, *, problem: str, slug: str, workspace: Path,
) -> "tuple[int | None, str | None, bool]":
    """Shared source-of-truth for citation eligibility (#8 / P2): classify a
    `import Problems.<problem>.proofs.L_<slug>` reference once, so the
    commit-time gate (`pipeline._cite_gate`) and the in-spawn `validate_file`
    submission mirror (`lsp.gateway`) never disagree on whether a cited
    sibling is citable.

    Returns `(goal_id, status, orphan)`:
      - `goal_id` / `status`: the cited goal's id + `goals.status`. An ALIAS
        goal (its `L_<slug>.lean` body delegates `apply <canonical>`, so it
        is sorry-free and its cite-safety is the CANONICAL's proved-ness, not
        the alias row's own status) is resolved through `alias_target_id` to
        the canonical, whose id + status is reported. So a proved alias is
        citable, and an alias to an open/shelved canonical inherits that
        goal's auto-link / reject handling. `(None, None)` when no goal
        tracks the slug.
      - `orphan`: True iff no goal tracks the slug AND
        `proofs/L_<slug>.lean` exists on disk — a stub whose row never
        committed (lake imports it fine and its `sorry` only warns, so
        citing it silently fake-proves the citer). When status is None and
        orphan is False the slug is a typo / cross-problem ref (lake's
        "unknown identifier" catches it).

    Bug history: the pre-2026-07-03 query filtered `alias_target_id IS NULL`,
    which excluded alias goals entirely — a proved alias then matched no row
    and (its `L_` file existing) was misclassified as an orphan stub, so
    citing it hit `cite_unproved_sibling` even though it is proved + sorry-
    free. Surfaced by mayer_vietoris `mv_delta` (a proved δ aliased to a
    byte-identical canonical), which blocked the MV LES assembly for 10
    attempts."""
    row = conn.execute(
        "SELECT id, status, alias_target_id FROM goals"
        " WHERE problem = ? AND slug = ?",
        (problem, slug),
    ).fetchone()
    if row is not None:
        # Resolve alias chains (alias → … → canonical) with a visited guard.
        cur = row
        seen: set[int] = set()
        while cur["alias_target_id"] is not None and int(cur["id"]) not in seen:
            seen.add(int(cur["id"]))
            nxt = conn.execute(
                "SELECT id, status, alias_target_id FROM goals WHERE id = ?",
                (int(cur["alias_target_id"]),),
            ).fetchone()
            if nxt is None:
                break
            cur = nxt
        return int(cur["id"]), str(cur["status"]), False
    orphan = (problem_dir(workspace, problem)
              / "proofs" / f"L_{slug}.lean").exists()
    return None, None, orphan


