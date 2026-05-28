---
problem: LinearAlgebra.lu_decomposition
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.lu_decomposition — LU factorization of a matrix with nonsingular leading principal submatrices

## Statement
∀ {n : ℕ} {𝕜 : Type} [Field 𝕜] (A : Matrix (Fin n) (Fin n) 𝕜),
  (∀ k (hk : k ≤ n),
    (A.submatrix (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0) →
  ∃ L U : Matrix (Fin n) (Fin n) 𝕜,
    L.BlockTriangular (fun i => (n - 1 : ℕ) - (i : ℕ)) ∧
    U.BlockTriangular (fun i : Fin n => (i : ℕ)) ∧
    (∀ i, L i i = 1) ∧
    A = L * U

## Setting
- Square matrix `A : Matrix (Fin n) (Fin n) 𝕜` over a field `𝕜`.
- Hypothesis `h k hk`: every leading `k × k` principal submatrix of `A` (for `k ≤ n`)
  is nonsingular. This is the standard condition under which the unpivoted LU
  factorization exists and is unique.
- Conclusion: factor `A = L * U` where
  - `L` is **unit lower triangular** (encoded via `BlockTriangular` with the
    reverse-`Fin` ordering `(n-1) - i`, mirroring the Cholesky problem's pattern),
  - `U` is **upper triangular** (`BlockTriangular id`),
  - `L i i = 1` for all `i` (unit diagonal on `L`).

This is the classical "no-pivoting" LU; the more general `PA = LU` (which holds for
any invertible matrix without the principal-submatrix hypothesis) is intentionally
**out of scope** — it requires permutation-matrix machinery and a constructive choice
of pivot order during elimination, which inflates the proof significantly.

## Lemma hints

mathlib does NOT contain a pre-built LU primitive (unlike LDL → Cholesky). Foundational
relevant modules:

- `Mathlib/LinearAlgebra/Matrix/Block.lean` — `Matrix.BlockTriangular` definition,
  `det_of_upperTriangular`, `det_of_lowerTriangular`, `upper_two_blockTriangular`
  (the 2×2 block decomposition lemma, key for the inductive step).
- `Mathlib/LinearAlgebra/Matrix/NonsingularInverse.lean` — `Matrix.det_ne_zero_iff_isUnit`,
  `Matrix.isUnit_iff_isUnit_det`, characterizations of invertible matrices.
- `Mathlib/LinearAlgebra/Matrix/Determinant/Basic.lean` — `Matrix.det_fin_succ_above`,
  block-determinant lemmas for the inductive step.
- `Mathlib/LinearAlgebra/Matrix/PosDef.lean` — positive-definite matrices satisfy
  the principal-minor hypothesis automatically; useful only as a special case for
  cross-checking (not a proof route).
- `Mathlib/Data/Matrix/Block.lean` (`Matrix.fromBlocks`) — assemble L and U from
  blocks during the induction.

## Strategic notes

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
