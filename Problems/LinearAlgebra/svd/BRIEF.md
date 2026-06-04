# LinearAlgebra.svd — BRIEF

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
Standard textbook proof skeleton (agents may follow or deviate):

1. `T† ∘ T : E →ₗ[𝕜] E` is positive self-adjoint.
2. Apply `IsSymmetric.eigenvectorBasis` (or similar) to obtain an orthonormal basis `b_E` of
   `E` diagonalising `T† ∘ T` with eigenvalues `λ_i = (singularValues T i)²`.
3. For the indices `i` where `λ_i > 0` (equivalently `i < rank T`), define
   `u_i := T(b_E i) / σ_i` (where `σ_i := singularValues T i`). Verify `{u_i}` is
   orthonormal in `F`.
4. Extend `{u_i}_{i < rank T}` to an orthonormal basis `b_F` of `F` (any orthonormal
   completion; mathlib has helpers for this).
5. In bases `(b_E, b_F)`, verify the matrix is diagonal with `σ_i` entries.

Proof angle is the agents' choice. The above is one route; alternatives include going via
`PosPart` / continuous functional calculus, or constructing the basis pair via the joint
diagonalisation of `T† ∘ T` and `T ∘ T†`.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct any foundational layer (singular values, spectral
   theorem, orthonormal basis machinery, adjoint, etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did not
`Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- Citing Jordan normal form / polar decomposition (mathlib lacks them; would be circular
  side quests).
- Citing the entire result as a single mathlib theorem if you find one (surface via
  `RequestUserAmend` — the problem is then done).

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
