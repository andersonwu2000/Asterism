---
problem: Geometry.stokes_dd_zero
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_dd_zero — d ∘ d = 0 for the manifold exterior derivative

## Statement
`mextDeriv I (mextDeriv I φ) = 0` for every smooth `k`-form `φ`. Owns `mextDeriv`,
the exterior derivative assembled from `mextDerivFun` (P5) + its smoothness.

## Setting
PARKED until P4 + P5 migrate. `mextDeriv = ⟨mextDerivFun, P5-smoothness⟩`.
`d ∘ d = 0` is the necessary correctness check on the chart-transport `d`.

## Lemma hints
- mathlib `extDerivWithin_extDerivWithin` / `extDeriv_extDeriv` (`d∘d=0` on the
  normed-space model) transported through the chart, OR the intrinsic naturality of
  `d` under pullback.
- `ContMDiffSection.ext` / section equality is pointwise; reduce `mextDeriv²φ = 0` to
  the model identity at each `extChartAt I x x` via the trivialisation round-trip.
- Provability relies on chart-independence of `mextDerivFun` — the construction must
  agree across overlapping charts for `d∘d=0` to hold intrinsically.
