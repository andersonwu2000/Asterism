---
problem: LinearAlgebra.sylvester_criterion
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.sylvester_criterion — Sylvester's criterion

## Statement
∀ {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ),
  M.IsHermitian →
  (M.PosDef ↔ ∀ k : Fin n, 0 < leadingPrincipalMinor M k)

## Setting
- `M` a real `n × n` matrix, assumed symmetric (`M.IsHermitian`, which over `ℝ`
  is `Mᵀ = M`).
- `leadingPrincipalMinor M k` (in `Defs.lean`): the determinant of the top-left
  `(k+1) × (k+1)` block of `M` (the inclusion `Fin (k+1) ↪ Fin n` is `Fin.castLE`).
- Conclusion (**Sylvester's criterion**): `M` is positive definite iff all `n`
  leading principal minors (the determinants of the `1×1, 2×2, …, n×n` top-left
  blocks) are strictly positive.

## Route

Two directions; the `→` direction is short (cite mathlib), the `←` direction is
the real work (induction reusing the Cholesky / LDL Library).

1. **`→` (PosDef ⇒ minors > 0).** Each leading block is `M.submatrix incl incl`
   with `incl = Fin.castLE _` **injective** (`Fin.castLE_injective`). So the block
   is positive definite by `Matrix.PosDef.submatrix`, and a positive-definite
   matrix has positive determinant by `Matrix.PosDef.det_pos`
   (`Mathlib/Analysis/Matrix/PosDef.lean`). Done in a few lines — mostly a
   reuse/dedupe exercise.
2. **`←` (symmetric ∧ minors > 0 ⇒ PosDef).** Induction on `n`. The top-left
   `(n-1)×(n-1)` block is symmetric and its leading minors are the first `n-1`
   minors of `M` (all `> 0`), so by the induction hypothesis it is positive
   definite. Extend to the full matrix via the block `LDLᵀ` factorisation: the
   final pivot `D_{n-1,n-1} = det(M) / det(M_{n-1}) > 0` (ratio of consecutive
   leading minors), so `M = L Dᴰ Lᵀ` with positive diagonal `D` ⇒ `M` positive
   definite. Reuse the **Cholesky / LDL Library (#40)** for the factorisation
   rather than rebuilding it.

## Lemma hints

Mathlib (cite, do not reconstruct):
- `Matrix.PosDef`, `Matrix.PosDef.submatrix`, `Matrix.PosDef.isHermitian`
  (`Mathlib/LinearAlgebra/Matrix/PosDef.lean`).
- `Matrix.PosDef.det_pos` (`Mathlib/Analysis/Matrix/PosDef.lean`).
- `Fin.castLE`, `Fin.castLE_injective`, `Matrix.submatrix`, `Matrix.det`.
- `Matrix.IsHermitian`, real-case `conjTranspose = transpose`.

Library (cite, do not reconstruct):
- `Library.LinearAlgebra.Cholesky.*` (#40) — the `LDLᵀ` / Cholesky factorisation
  for the `←` induction step. Read `Library/INDEX.md` for exact decl names.

## R1 — search before reconstructing (hard rule)

Before introducing any new `lemma`/`def`: `Grep` mathlib + `loogle`; reuse +
thin bridge if a match exists. Do NOT rebuild positive-definiteness theory, the
determinant API, or the Cholesky/LDL factorisation (Library #40).
`leadingPrincipalMinor` is the ONE intended local definition (already in
`Defs.lean`). New Forwards must open with
`## Forward rationale — Grep + Loogle confirmed missing: <keywords>`.

## Forbidden angles
- Searching mathlib for a ready-made Sylvester's criterion — there is none
  (confirmed missing). If you DO find one, surface via `RequestUserAmend`.
- Re-deriving the Cholesky / LDL factorisation instead of citing Library #40.
