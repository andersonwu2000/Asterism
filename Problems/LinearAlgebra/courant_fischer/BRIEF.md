# LinearAlgebra.courant_fischer — BRIEF

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
- **LinearAlgebra.rational_canonical_form** (19 decls) — keystone `Library.LinearAlgebra.RationalCanonicalForm.RationalCanonicalForm.main`
- **LinearAlgebra.sylvester_criterion** (20 decls) — keystone `Library.LinearAlgebra.SylvesterCriterion.main`
