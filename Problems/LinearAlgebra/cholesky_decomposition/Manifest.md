---
problem: LinearAlgebra.cholesky_decomposition
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.cholesky_decomposition — Cholesky decomposition of a positive-definite matrix

## Statement
∀ {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ),
  A.PosDef →
  ∃ L : Matrix (Fin n) (Fin n) ℝ,
    L.BlockTriangular (fun i => (n - 1 : ℕ) - (i : ℕ)) ∧
    A = L * Matrix.transpose L

## Setting
- Real `n × n` matrix `A` that is positive-definite (`Matrix.PosDef A`).
- Conclusion: factor `A = L * Lᵀ` where `L` is lower-triangular (encoded as block-
  triangular with the reverse-ordering function `(n-1) - i`, which on `Fin n` puts the
  "below-diagonal" entries on the kept side).
- The `L` is automatically real-positive-on-diagonal under the standard construction;
  this Manifest does not require asserting the diagonal-positivity explicitly (the
  factorization existence is the canonical theorem).

Mathlib already has the LDL decomposition for positive-definite matrices
(`Mathlib/Analysis/Matrix/LDL.lean`); Cholesky is a clean corollary by absorbing the
diagonal `D` into `L` as `L' := L * sqrt(D)` so that `A = L' * (L')ᵀ`.

## Lemma hints

Likely relevant mathlib modules:

- `Mathlib/Analysis/Matrix/LDL.lean` — `LDL.lower`, `LDL.diag`, `LDL.lower_inv`,
  the existing `S = LDLᴴ` decomposition (already proved for `PosDef`).
- `Mathlib/Analysis/Matrix/PosDef.lean` — `Matrix.PosDef`, related characterizations.
- `Mathlib/LinearAlgebra/Matrix/Block.lean` — `Matrix.BlockTriangular` definition.
- `Mathlib/Analysis/InnerProductSpace/Spectrum.lean` — spectral theorem (alternative
  proof route via diagonalising `A`, taking `√` on eigenvalues, etc.).

## Strategic notes

Two reasonable proof routes (agents' choice):

1. **Reduce to LDL**: cite mathlib's existing `LDL.lower` + `LDL.diag`, take the
   positive square root of `D` (diagonal entries are positive for `PosDef`), absorb
   into `L`. Smallest scope, leans heaviest on existing mathlib infrastructure.
2. **Spectral construction**: diagonalise `A` via the symmetric spectral theorem,
   take `√` on the eigenvalue diagonal, construct `L` from the eigenbasis. More
   self-contained but reconstructs work mathlib already has.

Route 1 is preferred unless mathlib's LDL exposes only `L⁻¹` (then absorbing the
square root may need a small inversion step).

### R1 — search before reconstructing (hard rule)

Before injecting any new `lemma` / `def` / `structure` / `class`:

1. `Grep` mathlib (`.lake/packages/mathlib/Mathlib/**`) for the type / functor / theorem
   name you intend to build, plus synonym variants. Any hit → `Read` to confirm semantics.
2. `python -m Tooling.knowledge.loogle <query>` for a statement-shape second pass.
3. If a match or near-match exists: **reuse it; write a thin bridge lemma** to this
   problem's naming. Do not reconstruct any foundational layer (LDL, positive square
   root on diagonal matrices, spectral theorem, etc.).
4. Only after confirmed missing, inject a new Forward. The `## Forward rationale` first
   line must state `Grep + Loogle confirmed missing` and list the exact keywords
   searched.

Strategist: when a Forward output is an obvious mathlib candidate that the agent did
not `Grep`, `ConfirmShelve` it and re-inject a Forward requiring the search step first.

### Forbidden angles

- Building Cholesky from scratch via Gram-Schmidt orthogonalisation when LDL is
  already in mathlib (Route 1 is the smaller scope).
- Citing the entire result as a single mathlib theorem if you find one (surface via
  `RequestUserAmend`).
