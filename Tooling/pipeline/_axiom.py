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

from dataclasses import dataclass
from pathlib import Path

from ._lake import lean_path_to_module


@dataclass
class AxiomGateResult:
    """Outcome of `axiom_gate`. `ok` is True iff the file elaborates clean
    AND its proof term is axiom-clean (no `sorryAx`, no rogue axioms).
    `failure_reason` / `detail` classify a failure for the caller's abort:
      - 'lake_build_error' — infra error / error diagnostics
      - 'axiom_violation'  — sorryAx tripwire or rogue axioms
    `verify` is the raw gateway result (carries `olean_written`, `axioms`)."""
    ok: bool
    failure_reason: str | None = None
    detail: str | None = None
    verify: dict | None = None


def _read_session_token(attempts_dir: "Path | None") -> str:
    """The pipeline's own gateway session token, if it still holds one
    (written at register_session, removed at WorkArea teardown). Empty
    string ⇒ run the gate on a borrowed slot (defensive fallback)."""
    if attempts_dir is None:
        return ""
    try:
        tok = attempts_dir / "_gateway_session.token"
        if tok.is_file():
            return tok.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def axiom_gate(
    path: Path, *, fq_name: str, whitelist: "list[str]",
    workspace: Path, attempts_dir: "Path | None" = None,
    write_olean: bool = True,
) -> AxiomGateResult:
    """The single soundness gate for flipping a goal 'proved' — elaborate
    `path` on the pipeline's OWN warm slot (via its session token; else
    borrow) and check the proof term's axioms.

    Two checks, mirroring Backward's leaf-bypass gate (backward.py:1005-1035):
      1. UNCONDITIONAL `sorryAx` tripwire — a transitive sorry (a cited stub /
         orphan sibling) compiles green (warning, not error); `collectAxioms`
         is ground truth. Catches what a literal `\\bsorry\\b` scan cannot
         (`admit`, imported sorry, macro-hidden sorry).
      2. Rogue-axiom check — only when `whitelist` is non-empty (matches the
         Backward gate; the root integrity gate applies FRAMEWORK_DEFAULT_AXIOMS
         separately as the whole-tree backstop).

    Runs on the OWN slot (`verify_in_session`) when a session token is present
    — the pipeline still holds its slot at commit time, so this is a warm
    ~50-200ms probe with no eviction (vs a cold borrow that evicts a random
    tenant, the 2026-06-29 slot-thrash bug). `write_olean=True` also publishes
    the .olean so downstream cold imports (cite-gate, harvest, root probe)
    don't rebuild it."""
    from ..lsp import lifecycle as gateway_lifecycle
    token = _read_session_token(attempts_dir)
    if token:
        v = gateway_lifecycle.verify_in_session(
            token, path.read_text(encoding="utf-8"),
            write_olean=write_olean, axioms_for=fq_name, workspace=workspace,
            _retry_delays=gateway_lifecycle._VERIFY_RETRY_DELAYS)
    else:
        v = gateway_lifecycle.verify_file(
            path, write_olean=write_olean, axioms_for=fq_name,
            workspace=workspace)
    if "error" in v:
        return AxiomGateResult(False, "lake_build_error",
                               f"verify infra error: {v['error']}", v)
    if not v.get("ok"):
        err = "\n".join(
            f"line {d.get('line','?')}:{d.get('col','?')}  "
            f"{d.get('severity','?')}: {d.get('message','')}"
            for d in (v.get("diagnostics") or [])
            if d.get("severity") == "error")
        return AxiomGateResult(False, "lake_build_error",
                               err or "(no error diagnostics returned)", v)
    if "sorryAx" in (v.get("axioms") or []):
        return AxiomGateResult(
            False, "axiom_violation",
            "proof term depends on sorryAx — a transitive sorry (e.g. a cited "
            "stub / orphan sibling), not a complete proof", v)
    if whitelist:
        if v.get("axiom_error"):
            return AxiomGateResult(False, "axiom_violation",
                                   f"axiom probe error: {v['axiom_error']}", v)
        rogue = set(v.get("axioms") or []) - set(whitelist)
        if rogue:
            return AxiomGateResult(False, "axiom_violation",
                                   f"rogue axioms: {sorted(rogue)}", v)
    return AxiomGateResult(True, verify=v)


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
    from ..lsp import lifecycle as gateway_lifecycle
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
