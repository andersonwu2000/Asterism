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


def canonicalize_anchor_pending(conn, workspace: Path, problem: str,
                                pending: "list[dict]") -> "list[dict]":
    """Rewrite framework-internal strategy names (`Problems.<problem>.s<N>`)
    in a pending-anchor list to their public goal slug, then dedup by name.

    `s<N>` is strategy id N; its goal's slug is the human-facing public name
    (the `L_<slug>.lean` re-export `def <slug> := @s<N>`). The kernel walk
    surfaces whatever a statement literally cites — often the internal `s<N>`
    (a proof cited the strategy term directly), sometimes BOTH the public
    alias AND `s<N>`. Leaving `s<N>` raw (a) leaks framework internals into the
    human sign-off surface and (b) BREAKS `asterism reject`: reject resolves a
    decl via its GOAL slug and `_find_reject_victims` matches `c["name"]`
    against the goal's fqn — never `s<N>` — so a lone-`s<N>` anchor is
    un-rejectable and its dependent deliverables silently escape the cascade.
    Canonicalizing to the public slug fixes display + reject together.

    The kernel walk (TCB) is untouched — this is a faithful RENAME of already-
    computed entries. Unmappable `s<N>` (no strategy row / goal) stay as-is.
    Returns a new list; the input is not mutated."""
    import re
    sre = re.compile(rf"^Problems\.{re.escape(problem)}\.s(\d+)$")
    out: list[dict] = []
    seen: set[str] = set()
    for c in pending:
        name = c.get("name", "")
        m = sre.match(name)
        if m:
            row = conn.execute(
                "SELECT g.slug AS slug, g.lean_path AS lean_path FROM goals g "
                "JOIN strategies st ON st.goal_id = g.id "
                "WHERE st.id = ? AND g.problem = ?",
                (int(m.group(1)), problem)).fetchone()
            if row and row["slug"]:
                mod = c.get("module")
                try:
                    mod = lean_path_to_module(
                        workspace, workspace / row["lean_path"])
                except (ValueError, OSError):
                    pass
                c = {**c, "name": f"Problems.{problem}.{row['slug']}",
                     "module": mod}
                name = c["name"]
        if name in seen:
            continue
        seen.add(name)
        out.append(c)
    return out


# Compiler-manufactured companion suffixes of an inductive/structure
# declaration. Their content is kernel-derived from the parent decl —
# vouching the parent vouches them — so the review PRESENTATION folds
# them into the parent. Constructor names are NOT here: constructors
# ARE the content under review (Lean rejects user constructors that
# shadow these names, so the set is unambiguous).
_GENERATED_COMPANIONS = frozenset({
    "rec", "recOn", "casesOn", "brecOn", "binductionOn",
    "below", "ibelow", "noConfusion", "noConfusionType",
})


def fold_generated_companions(
        pending: "list[dict]") -> "tuple[list[dict], int]":
    """Presentation-layer fold (#71-class noise, inductive edition): drop
    a pending entry when it is a compiler-generated companion (`X.rec`,
    `X.casesOn`, `X.brecOn.go`, ...) of an inductive/structure `X` that
    is ITSELF a pending entry — the kernel derives the companion's
    meaning entirely from `X`'s constructors, so the human vouches it by
    vouching `X`.

    Fail-closed: an entry whose parent is not in the list as an
    `induct` (or that is itself a `ctor`) is kept. The kernel walk,
    `asterism reject` cascade, and harvest all consume the RAW closure —
    this reshapes the human-facing list only.

    Returns (folded_list, dropped_count); the input is not mutated."""
    inducts = {c.get("name", "") for c in pending
               if c.get("kind") == "induct"}
    out: list[dict] = []
    dropped = 0
    for c in pending:
        parts = c.get("name", "").split(".")
        # Parent prefix + a companion component right after it (deeper
        # components — `brecOn.go` — ride along with their companion).
        fold = c.get("kind") != "ctor" and any(
            ".".join(parts[:i]) in inducts
            and parts[i] in _GENERATED_COMPANIONS
            for i in range(1, len(parts)))
        if fold:
            dropped += 1
        else:
            out.append(c)
    return out, dropped
