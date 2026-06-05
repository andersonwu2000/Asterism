---
problem: LinearAlgebra.courant_fischer
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# LinearAlgebra.courant_fischer — Courant–Fischer min-max theorem

## Statement
∀ {E} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
  {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n),
  hT.eigenvalues hn k =
    ⨆ S : {U : Submodule ℝ E // Module.finrank ℝ U = (k : ℕ) + 1},
      ⨅ x : {v : E // v ∈ (S : Submodule ℝ E) ∧ v ≠ 0},
        ⟪T x, x⟫_ℝ / ‖x‖ ^ 2

## Setting
- `E` finite-dim real inner product space; `T : E →ₗ[ℝ] E` symmetric (`hT`).
- `hT.eigenvalues hn` (mathlib `LinearMap.IsSymmetric.eigenvalues`,
  `Analysis/InnerProductSpace/Spectrum.lean`): the `n` eigenvalues **sorted in
  decreasing order**, indexed by `Fin n`.
- Conclusion (**Courant–Fischer**, max–min form): the `k`-th eigenvalue (k-th
  largest) is the max over `(k+1)`-dim subspaces of the min Rayleigh quotient
  over that subspace's nonzero vectors. (k=0 recovers the largest eigenvalue =
  `⨆` Rayleigh; k=n−1 the smallest.)

## Route

mathlib has the k=0 / k=n−1 extremes (`Analysis/InnerProductSpace/Rayleigh.lean`:
`iSup`/`iInf` Rayleigh = top/bottom eigenvalue) and the sorted `eigenvalues` +
`eigenvectorBasis` (`Spectrum.lean`), but NOT the general k-th min-max. The work
is the dimension-counting argument that bridges them.

1. **Diagonalize (cite).** `hT.eigenvectorBasis` gives an orthonormal eigenbasis
   `e₀,…,e_{n−1}` with `T eᵢ = (eigenvalues i) • eᵢ`. On the span of any subset,
   the Rayleigh quotient is a convex combination of the corresponding eigenvalues,
   so it is bounded between the min and max eigenvalue of that subset.
2. **`≥` (exhibit a witness subspace).** Take `S₀ = span {e₀,…,e_k}`
   (`finrank = k+1`); every nonzero `x ∈ S₀` has Rayleigh `≥ eigenvalues k`
   (smallest eigenvalue in the block), so `⨅` over `S₀ ≥ eigenvalues k`, hence the
   `⨆` over all such `S` is `≥ eigenvalues k`.
3. **`≤` (dimension pigeonhole).** For ANY `(k+1)`-dim `S`, `S ∩ span{e_k,…,e_{n−1}}`
   (dim `n−k`) is nonzero by dimension count (`(k+1)+(n−k) > n`); a nonzero `x`
   there has Rayleigh `≤ eigenvalues k`, so `⨅` over `S ≤ eigenvalues k`, hence
   the `⨆` is `≤ eigenvalues k`.

## Lemma hints

Mathlib (cite, do not reconstruct):
- `LinearMap.IsSymmetric.eigenvalues`, `…eigenvectorBasis`,
  `…eigenvectorBasis_apply_self_apply`, `…apply_eigenvectorBasis`
  (`Analysis/InnerProductSpace/Spectrum.lean`).
- `LinearMap.IsSymmetric.hasEigenvalue_iSup_of_finiteDimensional` /
  `…iInf…` and `ContinuousLinearMap.rayleighQuotient`
  (`Analysis/InnerProductSpace/Rayleigh.lean`).
- `Submodule.finrank`, `Submodule.finrank_add_inf_finrank_le` /
  dimension-pigeonhole lemmas, `OrthonormalBasis`, `inner`, `norm_sq`.
- `ciSup`/`ciInf` API (`Real` is conditionally complete) for the sup/inf over
  subspaces and vectors.

## R1 — search before reconstructing (hard rule)

Before any new `lemma`/`def`: `Grep` mathlib + `loogle`; reuse + thin bridge.
Do NOT rebuild the spectral theorem, the eigenvector basis, or the Rayleigh
extremes. New Forwards must open with
`## Forward rationale — Grep + Loogle confirmed missing: <keywords>`.

## Forbidden angles
- Searching mathlib for a ready-made Courant–Fischer / general min-max — only the
  k=0/k=n−1 extremes exist. (If you find the general form, `RequestUserAmend`.)
- Re-deriving the finite-dim spectral theorem instead of citing `Spectrum.lean`.
