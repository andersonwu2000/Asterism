# LinearAlgebra.lu_decomposition — BRIEF

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
The natural proof is **induction on `n`**:

1. **Base case** (`n = 0`): trivial, take `L = U = 1` (or the unique empty matrix).
2. **Inductive step** (`n → n + 1`): write `A` as a 2×2 block
   ```
   A = ⎡ a₁₁   v ⎤
       ⎣  w    Aₛ ⎦
   ```
   where `a₁₁ ≠ 0` (from the `k = 1` hypothesis) and `Aₛ : Matrix (Fin n) (Fin n) 𝕜`
   is the trailing submatrix. The Schur complement `Aₛ - (1/a₁₁) • (w ⬝ vᵀ)`
   has leading principal submatrices that inherit nonsingularity from `A`'s.
   Apply IH to get its `L', U'`; assemble:
   ```
   L = ⎡  1                0  ⎤    U = ⎡ a₁₁     v    ⎤
       ⎣ w/a₁₁             L' ⎦        ⎣  0      U'   ⎦
   ```
   and verify `L * U = A` block-by-block + the triangular conditions transfer
   under `Matrix.fromBlocks`.

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct foundational layers (block-matrix arithmetic,
   Schur complement identities, determinant of block-triangular matrices, etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords
   searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did
not `Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- **Permutation/pivoting machinery**: do not introduce `Equiv.Perm` or `PEquiv` to
  factor permutations into the proof. The unpivoted hypothesis is sufficient.
- **Reconstructing block-matrix arithmetic** (`fromBlocks`, block multiplication,
  block determinant) from scratch — mathlib has these in
  `Mathlib/Data/Matrix/Block.lean` and `Mathlib/LinearAlgebra/Matrix/Block.lean`.
- **Spectral / eigenvalue route**: LU is a structural elimination result; bringing
  in eigenvalues / diagonalization is the wrong angle and likely won't close.

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
