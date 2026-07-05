---
problem: Geometry.stokes_theorem
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_theorem — the generalized Stokes theorem on a manifold with boundary

## Statement
The capstone: for a compact oriented `(n+1)`-manifold-with-boundary `M` (with compact
boundary `∂M`) and any smooth `n`-form `φ`, `∫_M dφ = ∫_∂M ι*φ` — both sides the single
`DiffForm.integral` operator (`mextDeriv φ` on `M`, `pullbackBdry φ` on `∂M`). Owns
`pullbackBdry` (the assembled `ι*`) and `instBdryOriented` (`∂M`'s `OrientedManifold`
instance). Cites the whole tower.

## Setting
`mextDeriv` (P6, `Library.Geometry.Manifold.DDZero`) is the exterior derivative;
`pullbackBdry` assembles P10's `pullbackBdryFun` + `contMDiff_pullbackBdryFun`
(`Library.Geometry.ManifoldBdry.{PullbackBdryDefs, PullbackFormContMDiff}`);
`DiffForm.integral` + `OrientedManifold` are P11 (`StokesIntegralDefs`); `∂M`'s orientation
is P12b's `inducedOrient` / `inducedOrient_ne_zero` (`InducedOrientNonzero`).

## Lemma hints
- Both sides are `DiffForm.integral` (P11): `∫_N μ = ∫ topCoeff` against the reference form;
  `localCoeff`/`topCoeff` are coordinate readouts. Use linearity of `DiffForm.integral`,
  `mextDeriv`, and `pullbackBdry` to reduce to a single POU-bump-supported `φ`.
- Smooth partition of unity on `M` subordinate to an atlas of boundary + interior charts
  (`SmoothPartitionOfUnity.exists_isSubordinate_chartAt_source`); `φ = ∑ᶠ f_i • φ`,
  each `f_i • φ` supported in one chart.
- Interior chart (support in `interior M`): `∫_M d(f_i•φ) = 0` (compactly-supported exact
  form, divergence theorem on `ℝ^{n+1}` / `MeasureTheory.integral_deriv_eq_zero`-style) and
  `∫_∂M ι*(f_i•φ) = 0` (support disjoint from `∂M`).
- Boundary chart (half-space `{x₀ ≥ 0}`): in coordinates `d(f_i•φ)` integrates by the
  fundamental theorem of calculus in the `x₀` slot
  (`intervalIntegral.integral_deriv_eq_sub` / `MeasureTheory.integral_Iic_deriv`), leaving
  the face integral over `{x₀ = 0}` — which is `∫_∂M ι*(f_i•φ)` via `formInCoord` /
  `faceEmbedL` (`MExtDerivCoord.form_in_coord_mext_deriv_eq`, the coordinate `extDerivWithin`).
- Sum over `i` telescopes the boundary terms; interior bumps cancel. `mextDeriv φ` has degree
  `n+1` (top form on `M`), `pullbackBdry φ` degree `n` (top form on `∂M`).
- `Library.Geometry.Manifold.MExtDerivCoord.{formInCoord, form_in_coord_mext_deriv_eq,
  ext_deriv_locality_pullback}`; `DDZero.mextDeriv`; `StokesIntegralDefs.DiffForm.integral`.
