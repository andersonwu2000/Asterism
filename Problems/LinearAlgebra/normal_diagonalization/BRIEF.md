# LinearAlgebra.normal_diagonalization — BRIEF

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
Standard textbook route (Schur ⇒ spectral), reusing our Library:

1. **Triangularize via Library Schur**: cite
   `Library.LinearAlgebra.SchurTriangularization.Triangularization.main` to get a basis in
   which `T` is upper triangular (the invariant flag). ℂ is `IsAlgClosed`.
2. **Orthonormalize keeping the flag**: Gram-Schmidt that basis to an orthonormal basis
   `e`. Because Gram-Schmidt preserves each initial-segment span, the flag is preserved, so
   `toMatrix e e T` is still upper triangular.
3. **Normal + upper-triangular ⇒ diagonal**: an upper-triangular matrix `M` (in an
   orthonormal basis, so `Mᴴ` is the adjoint's matrix) with `Commute Mᴴ M` is diagonal —
   compare diagonal entries of `M Mᴴ` and `Mᴴ M` row by row (induction on the column).

Let the Backward agent commit to its angle; the Schur-citation + Gram-Schmidt skeleton
above is the suggested decomposition but not mandatory.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def`: `Grep` mathlib (and `Library/`) + `loogle` for
the result; reuse and write a thin bridge if it exists. A `## Forward rationale` first line
must read `Grep + Loogle confirmed missing` with the exact keywords. In particular, if
mathlib already states the **normal** spectral theorem under some name, surface it via
`RequestUserAmend` — the problem is then already done.

### Forbidden angles

- Reconstructing Schur from scratch — cite the Library entry above.
- Reconstructing Gram-Schmidt — it is in mathlib.

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
