# LinearAlgebra.jordan_normal_form — BRIEF

_Auto-rendered from `Manifest.md` + `Library/`. The framework_
_inlines this file into `Context.md` for every Builder /_
_Backward dispatch on this problem._

## Sandbox
- Reads allowed without permission prompts:
  - This goal's problem dir (your cwd).
  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on Mathlib source.
- Reads NOT allowed: other `Problems/<...>/` dirs — irrelevant to this goal. Use Loogle / Grep on Mathlib instead.
- `Context.md` + `PAST_*.md` companion files: read-only.
- `patch.lean` is your single output. Lead with `--` annotation comments, then edit the body (Builder fills in the proof; Backward edits the strategy skeleton's body — signature locked). See the kind-specific prompt for layout.

## Strategic notes (from Manifest.md)
The proof method is the agents' choice. The standard textbook chain:

1. **Primary decomposition**: over algClosed `K`, `V` decomposes as a direct sum of
   generalized eigenspaces `V = ⊕ ker((T - λ I)^n_λ)`. Mathlib gives the underlying
   `iSup` form; package it as an internal direct-sum decomposition for downstream use.
2. **Reduction to nilpotent**: on each generalized eigenspace `V_λ`, the operator
   `N := (T - λ I)` restricted to `V_λ` is nilpotent.
3. **Jordan basis for a nilpotent operator**: from the kernel filtration
   `ker N ⊆ ker N² ⊆ ... ⊆ ker N^d = V_λ`, build a Jordan basis (chains of vectors
   `v, N v, N² v, ...` ending at `0`). The matrix of `N` in this basis is the
   strictly-upper-triangular part of a Jordan-block diagonal.
4. **Assemble**: combine bases from each generalized eigenspace, shift by `λ I` on each
   block to recover `T`'s matrix as a Jordan form.

Other routes (Smith normal form on `K[x]`-module, semisimple+nilpotent split via
Chevalley–Jordan, abstract algebra angles) are valid too — the spine above is just the
most concrete classical path.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct any foundational layer (eigenspace machinery,
   nilpotent operator infrastructure, direct-sum decomposition, matrix↔basis conversion,
   etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords
   searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did not
`Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- Citing Smith normal form for `K[x]`-modules from mathlib if it would let you sidestep
  building the structural understanding (it would technically work but loses the stress
  signal — the point of this problem is to exercise the framework on a deep multi-stage
  decomposition, not to thread an algebraic shortcut). Avoid `Module.basisOfPid` /
  `Submodule.basisOfPid` family for this purpose.
- Citing a sibling problem (e.g. `Problems/LinearAlgebra/schur_triangularization`) —
  sandbox blocks cross-problem reads; each problem stands alone.
- Citing the entire result as a single mathlib theorem if one exists (surface via
  `RequestUserAmend`).

## Library available (reusable — proved in prior Problems)

Theorems Asterism already proved and harvested into `Library/`. **Prefer citing these over re-deriving.** To use one: `import <module>` (the dotted prefix before the decl's last component) and reference it by its full name. You have read access to `Library/` — grep there for exact signatures. The R1 search-before-reconstruct rule covers Library too.

Library modules in the `LinearAlgebra` domain (grep `Library/` for signatures):
- **LinearAlgebra.jordan_normal_form** (94 decls) — keystone `Library.LinearAlgebra.JordanForm.Basic.main`
- **LinearAlgebra.schur_triangularization** (29 decls) — keystone `Library.LinearAlgebra.SchurTriangularization.Triangularization.main`
- **LinearAlgebra.normal_diagonalization** (11 decls) — keystone `Library.LinearAlgebra.NormalDiagonalization.Spectral.main`
- **LinearAlgebra.svd** (18 decls) — keystone `Library.LinearAlgebra.SVD.Basic.main`
- **LinearAlgebra.polar_decomposition** (12 decls) — keystone `Library.LinearAlgebra.PolarDecomposition.main`
- **LinearAlgebra.primary_decomposition** (17 decls) — keystone `Library.LinearAlgebra.PrimaryDecomposition.Basic.main`
- **LinearAlgebra.invariant_factor_decomposition** (29 decls) — keystone `Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition.main`
