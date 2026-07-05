---
problem: Geometry.pullback_flat_smooth
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Geometry.pullback_flat_smooth — smoothness of the flat-form pullback representative

## Statement
∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F] {k : ℕ}
  (e : E → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ)),
  ContDiff ℝ ∞ e → ContDiff ℝ ∞ φ →
  ContDiff ℝ ∞ (fun x => (φ (e x)).compContinuousLinearMap (fderiv ℝ e x))

## Strategic notes
This is the analytic core of the integration-current bridge's first brick: the
pullback of a flat ambient `k`-form along a smooth map `e : E → F`, read in
coordinates. The existing boundary pullback (`contMDiff_pullbackBdryFun`) is the
template, but it has the *constant* coordinate derivative `faceEmbedL`; here the
derivative `fderiv ℝ e x` varies with `x`, which is the new ingredient.

Three independent pieces, each a natural sub-goal:

1. **`φ ∘ e` is smooth** — the form field composed with the map.
2. **`x ↦ fderiv ℝ e x` is smooth** — the derivative of a smooth map is itself
   smooth (one order is spent, but the target order is `∞`).
3. **The fibrewise composition is smooth in both arguments** — the map sending an
   alternating form `w` and a linear map `L` to `w.compContinuousLinearMap L`.
   This is the hard piece: it is *linear* in `w` but *degree-`k`* in `L`, so the
   fixed-`L` API (linear in `w` only) does not suffice; the joint smoothness must
   be assembled. This is a genuine gap above the boundary case.

Then combine 1–3 by composition. `e` and `φ` are given as smooth hypotheses — no
construction of either is required.
