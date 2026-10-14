/-
  Defs.lean — PARKED (not yet buildable). Owns `mextDeriv : DiffForm I M k →
  DiffForm I M (k+1)`, the exterior derivative as a genuine smooth form, assembled
  from `mextDerivFun` (P5) + its smoothness witness (P5's Root). The Root proves
  `d ∘ d = 0`.

  ⚠️ FINALIZE AFTER P4 + P5 MIGRATE: import/open P4 (`DiffForm`/`formBundleCore`) and
  P5 (`mextDerivFun` + the smoothness lemma — name TBD); set `contMDiff_toFun` to the
  cited P5 smoothness lemma applied to `I φ`.
-/
import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.Root
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_smooth
import Problems.Geometry.stokes_mextderiv.proofs.L_mext_deriv_triv_read

open scoped Manifold Bundle ContDiff
open Bundle
open Problems.Geometry.stokes_form_bundle (DiffForm)
open Problems.Geometry.stokes_mextderiv (mextDerivFun)

namespace Problems.Geometry.stokes_dd_zero

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- The exterior derivative of a smooth `k`-form, as a genuine smooth `(k+1)`-form:
    `mextDerivFun` (data, P5) + P5's smoothness witness. GENUINE (no `sorry`). -/
noncomputable def mextDeriv {k : ℕ} (φ : DiffForm I M k) : DiffForm I M (k + 1) where
  toFun := mextDerivFun I φ
  contMDiff_toFun := Problems.Geometry.stokes_mextderiv.main I φ

end Problems.Geometry.stokes_dd_zero
