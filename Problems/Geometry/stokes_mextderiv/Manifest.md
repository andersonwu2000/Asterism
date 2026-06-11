---
problem: Geometry.stokes_mextderiv
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.stokes_mextderiv — the exterior derivative is a smooth section

## Statement
`CMDiff ∞ (T% (mextDerivFun I φ))` — `mextDerivFun I φ` (the chart-transport of
mathlib's `extDerivWithin`) is a `C^∞` section of `⋀^(k+1) T*M`. (§A.5. Owns
`formInCoord` / `mextDerivFun`.)

## Setting
PARKED until P4 (`stokes_form_bundle`) migrates — `formInCoord`/`mextDerivFun` cite
P4's `DiffForm` / `formBundleCore` / fibre-bundle instances. Stated as a standalone
Root (not the inline `contMDiff_toFun` field of `mextDeriv`) so the bundle instances
are in scope for the `T%`/`CMDiff` section-smoothness elaborator.

## Lemma hints
- mathlib `Analysis/Calculus/DifferentialForm/Basic.lean` — `extDerivWithin`, its
  smoothness (`ContDiffOn`/`ContMDiff` of `extDerivWithin` of a smooth family).
- `ContMDiffSection` / `Bundle.contMDiff_section`, `Trivialization.symmL` /
  `continuousLinearMapAt` smoothness, `contMDiffAt_extChartAt`.
- Strategy: section smoothness reduces (via the trivialisation) to smoothness of the
  coordinate map `x ↦ extDerivWithin (formInCoord I φ x) (range I) (extChartAt I x x)`;
  `extDerivWithin` is smooth in the form when the form is smooth, and `φ` is smooth
  (it is a `ContMDiffSection`).
