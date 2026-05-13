"""Axiom probe — single source of truth for "is this proof clean".

Verifies that `#print axioms <fq_name>` returns a subset of the
manifest's `axioms_whitelist`. Returns (True, msg) iff clean.

THE invariant for `goals.status='proved'`: the DB row's status flips
to 'proved' iff `axiom_probe` returned ok on the goal's public name.
Every "mark proved" call site must run this and abort on failure.
Adding a new path that flips status without calling this is a
regression — `tests/test_axiom_invariant.py` enforces this.

Why lake build alone is insufficient: lake accepts files whose imports
contain `sorry`. The sorry'd module compiles fine; sorryAx propagates
through definitions to anything that uses them, but lake build returns
rc=0 throughout. Only `#print axioms` walks the dependency graph
through the kernel and reports every axiom touched.

Implementation: dispatches to the gateway's `/verify` endpoint, which
runs `Lean.collectAxioms` in the same warm worker that just elaborated
the file. Replaces the prior `lake build <module>` + `lake env lean
#print axioms` subprocess pair (~15-30s wall) with one in-worker call
(~3-5s on warm Mathlib, ~50-200ms when olean is fresh from a sibling
verify in the same slot). See `docs/archive/verify_unification.md`.
"""
from __future__ import annotations

from pathlib import Path

from ._lake import lean_path_to_module


def axiom_probe(
    workspace: Path,
    *,
    fq_name: str,
    module: str,
    whitelist: list[str],
    timeout: int = 180,
) -> tuple[bool, str]:
    """Verify `fq_name`'s transitive axiom set ⊆ `whitelist`.

    Returns:
      - (True, "axioms ok: [<sorted>]") on clean proof
      - (False, reason) otherwise. Reasons:
        * "no axioms_whitelist": Manifest didn't authorize bypass
        * "axiom probe failed: <exc>": gateway unreachable / timeout
        * "verify failed: <error>": elaborate produced error diagnostics
        * "rogue axioms: [<sorted>]": axioms used not in whitelist —
          almost always sorryAx, indicating transitive sorry import.
    """
    if not whitelist:
        return False, "no axioms_whitelist"

    # Resolve module name → source path. The gateway's /verify takes
    # a source path (it didChanges that content into a worker slot).
    source = workspace / Path(*module.split(".")).with_suffix(".lean")
    if not source.exists():
        return False, f"axiom probe failed: source not found: {source}"

    # Lazy import to avoid circular deps (gateway_lifecycle imports
    # nothing from pipeline, but pipeline package init shouldn't
    # depend on the daemon-side gateway module unconditionally).
    from .. import gateway_lifecycle
    result = gateway_lifecycle.verify_file(
        source, write_olean=True, axioms_for=fq_name,
        timeout=float(timeout), workspace=workspace,
    )

    if "error" in result:
        return False, f"axiom probe failed: {result['error']}"
    if not result.get("ok"):
        diags = result.get("diagnostics") or []
        msg = "; ".join(
            d.get("message", "")[:120] for d in diags
            if d.get("severity") == "error"
        )[:300]
        return False, f"verify failed: {msg or '(no error diagnostics returned)'}"
    if result.get("axiom_error"):
        return False, f"axiom probe failed: {result['axiom_error']}"
    used: set[str] = set(result.get("axioms") or [])
    rogue = used - set(whitelist)
    if rogue:
        return False, f"rogue axioms: {sorted(rogue)}"
    return True, f"axioms ok: {sorted(used) or '[]'}"


def axiom_probe_file(
    workspace: Path, dest: Path, *,
    problem: str, slug: str, whitelist: list[str],
) -> tuple[bool, str]:
    """Convenience wrapper: derive (fq_name, module) from a goal lean
    file + slug, then call `axiom_probe`. The standard call shape for
    Builder / verify_strategy / sub-goal-stub promotion."""
    fq_name = f"Problems.{problem}.{slug}"
    module = lean_path_to_module(workspace, dest)
    return axiom_probe(workspace, fq_name=fq_name, module=module,
                       whitelist=whitelist)
