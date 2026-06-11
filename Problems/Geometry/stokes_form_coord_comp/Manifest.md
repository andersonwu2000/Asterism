---
problem: Geometry.stokes_form_coord_comp
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_form_coord_comp — cocycle condition for the `⋀ᵏ T*M` transition

## Statement
`formCoordChange I k j l x (formCoordChange I k i j x v) = formCoordChange I k i l x v`
on the triple overlap. (§A.3 — the `coordChange_comp` field of the `VectorBundleCore`.)

## Setting
`formCoordChange I k i j x := compContinuousLinearMapCLM ((tangentBundleCore I M).coordChange j i x)`.
Because forms are contravariant, `formCoordChange i j` precomposes by the tangent
transition `j i`; the cocycle therefore reads with the indices as stated.

## Lemma hints
- `Mathlib/Geometry/Manifold/VectorBundle/Tangent.lean` — `tangentBundleCore`,
  `VectorBundleCore.coordChange_comp` (tangent cocycle `τ_jk ∘ τ_ij = τ_ik`).
- `ContinuousAlternatingMap.compContinuousLinearMapCLM` — contravariant functor:
  `compContinuousLinearMapCLM g ∘ compContinuousLinearMapCLM h = compContinuousLinearMapCLM (h ∘ g)`.
- Strategy: unfold both sides to precompositions, apply the contravariant
  functoriality, then close with the tangent cocycle at `(l, j, i)`.
