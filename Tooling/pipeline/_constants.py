"""Anchor closure probe — the anchor+claim architecture's TCB entry.

Given a fully-qualified name (a top-level *deliverable*: a claim or a
delivered def), returns its **pending-anchor closure**: the constants
its statement's meaning rests on that are NOT in the trust base
(Mathlib ∪ Library ∪ Lean/Std/Init core). Those are exactly the defs
the framework itself generated that a human must vouch for
(`docs/internal/anchor_claim_design.md` §4).

Complement to `_axiom.py`: `axiom_probe` gates the *proof*'s trust base
(no rogue axioms / transitive sorry); `anchor_closure` gates the
*statement*'s trust base (no unreviewed defs). Both round-trip through
the same warm gateway (`Asterism.anchorClosure` RPC — a kernel walk over
`Expr.getUsedConstants` + module provenance, NEVER a text/regex scan;
see the handler's docstring for why regex here would be a TCB hole).

The closure is computed against the terminal elaborated environment of
`module`'s source file, so `module` must be the file that *declares*
`fq_name` (e.g. the problem's Root.lean or a proof file), and it must
elaborate clean — a probe on a file with errors returns an error.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ._lake import lean_path_to_module


@dataclass
class AnchorClosure:
    """Result of an anchor-closure probe.

    `ok` is True iff the kernel walk ran (file elaborated clean and the
    constant resolved). `pending` is the list of non-trusted constants
    reachable from the deliverable's statement (each a dict with
    `name`, `module`, `kind`). `top_kind`/`top_module` describe the
    deliverable itself so a caller can present it as a claim
    (`top_kind == 'thm'`) vs a delivered anchor (any other kind)."""
    ok: bool
    error: str | None = None
    top_kind: str = ""
    top_is_prop: bool = False
    top_module: str = ""
    pending: list[dict] = field(default_factory=list)

    @property
    def top_is_claim(self) -> bool:
        """The deliverable is a *claim* iff its type is a `Prop`
        (a theorem, or the framework's `def main := proof` wrapper);
        otherwise it is a delivered data *anchor* the human must vouch
        for in full."""
        return self.top_is_prop

    @property
    def anchors(self) -> list[dict]:
        """Pending defs/data the human must vouch for (non-theorems)."""
        return [c for c in self.pending if c.get("kind") != "thm"]

    @property
    def claims(self) -> list[dict]:
        """Pending theorems in the closure (proved lemmas a delivered
        def's *body* depends on — surfaced as claims, opt-out
        rejectable like the deliverable itself)."""
        return [c for c in self.pending if c.get("kind") == "thm"]


def anchor_closure(
    workspace: Path,
    *,
    fq_name: str,
    module: str,
    timeout: int = 180,
) -> AnchorClosure:
    """Compute `fq_name`'s pending-anchor closure via the gateway.

    Args:
      fq_name: fully-qualified name of the deliverable (e.g.
        ``Problems.Geometry.foo.main``).
      module:  dotted module name of the source file that declares it
        (e.g. ``Problems.Geometry.foo.Root``). Resolved to a .lean
        path that the gateway swaps into a warm slot and elaborates.

    Returns an `AnchorClosure`. On any infrastructure / elaboration /
    resolution failure, `ok` is False and `error` explains — a caller
    presenting a review MUST treat `ok is False` as "cannot vouch yet"
    (never as "no anchors").
    """
    source = workspace / Path(*module.split(".")).with_suffix(".lean")
    if not source.exists():
        return AnchorClosure(ok=False,
                             error=f"anchor closure failed: source not found: {source}")

    # Lazy import to avoid pulling the daemon-side gateway module into
    # the pipeline package's import graph unconditionally (mirrors
    # `_axiom.axiom_probe`).
    from ..lsp import lifecycle as gateway_lifecycle
    result = gateway_lifecycle.verify_file(
        source, write_olean=False, constants_for=fq_name,
        timeout=float(timeout), workspace=workspace,
    )

    if "error" in result:
        return AnchorClosure(ok=False, error=f"anchor closure failed: {result['error']}")
    if not result.get("ok"):
        diags = result.get("diagnostics") or []
        msg = "; ".join(
            d.get("message", "")[:120] for d in diags
            if d.get("severity") == "error"
        )[:300]
        return AnchorClosure(
            ok=False,
            error=f"verify failed: {msg or '(no error diagnostics returned)'}",
        )
    if result.get("closure_error"):
        return AnchorClosure(ok=False,
                             error=f"anchor closure failed: {result['closure_error']}")
    return AnchorClosure(
        ok=True,
        top_kind=result.get("top_kind") or "",
        top_is_prop=bool(result.get("top_is_prop")),
        top_module=result.get("top_module") or "",
        pending=list(result.get("pending_anchors") or []),
    )


def anchor_closure_goal(
    workspace: Path, dest: Path, *, problem: str, slug: str,
    timeout: int = 180,
) -> AnchorClosure:
    """Convenience wrapper: derive (fq_name, module) from a goal's lean
    file + slug, then call `anchor_closure`. Mirrors
    `_axiom.axiom_probe_file`."""
    fq_name = f"Problems.{problem}.{slug}"
    module = lean_path_to_module(workspace, dest)
    return anchor_closure(workspace, fq_name=fq_name, module=module,
                          timeout=timeout)
