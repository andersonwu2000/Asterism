---
problem: Geometry.stokes_bdry_oriented
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_bdry_oriented — the induced boundary orientation vanishes nowhere

## Statement
`inducedOrient` (the induced boundary orientation form `ι_ν μ` on `∂M`, assembled as a
genuine smooth `n`-form from P12's POU-glued `inducedOrientFun` + its smoothness witness)
vanishes nowhere: `∀ p : Bdry n M, inducedOrient p ≠ 0`. This is `refForm_ne`, the last
obligation for `∂M`'s `OrientedManifold` instance (assembled in P13). Owns `inducedOrient`.

## Setting
The induced orientation contracts `M`'s nowhere-zero reference form `μ` with the outward
normal `ν = −e₀`, transverse to the boundary face `{x₀ = 0}`. Each chart-local candidate
`inducedOrientChartFun q` is therefore a nonzero top `n`-form, and (the cocycle / positive
normal derivative) all candidates at a point lie on the SAME positive ray. The POU glue
`∑ᶠ q, (pou q) • (chartFun q)` has nonnegative coefficients summing to `1`, so the convex
combination of same-ray nonzero vectors is nonzero — `ι_ν μ` vanishes nowhere.

## Lemma hints
- `inducedOrient p` unfolds to P12's `inducedOrientFun p =`
  `∑ᶠ q, inducedOrientPOU n M q p • inducedOrientChartFun q p`
  (`Library.Geometry.Manifold.InducedOrientDefs.{inducedOrientFun, inducedOrientPOU,
  inducedOrientChartFun}`).
- POU partition: `SmoothPartitionOfUnity.sum_eq_one` (coeffs sum to 1 at every point),
  `SmoothPartitionOfUnity.nonneg`; `inducedOrientPOU n M` is the chosen POU.
- Same-ray positivity: each `inducedOrientChartFun q p` (for `q` in the POU support at `p`)
  is a positive multiple of any other via the boundary coordinate-change cocycle with
  positive normal derivative `c = ∂τ⁰/∂x⁰ > 0`; the tangential defect dies by alternation
  (`AlternatingMap.map_linearDependent` — `range faceEmbedL` is `n`-dimensional in `n+1`).
- A nonneg-weighted (weights summing to 1) combination of nonzero vectors on a common open
  ray is nonzero; `finsum`/`Finset.sum` positivity (`Finset.sum_ne_zero` via a strictly
  positive coordinate), `ContinuousAlternatingMap` nonzero at a fixed `n`-frame.
- `inducedOrient` is `Library.Geometry.Manifold.DiffFormBundle.DiffForm` (a smooth section);
  `inducedOrient p = inducedOrientFun p` definitionally.
