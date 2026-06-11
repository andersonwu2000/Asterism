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
import Library.Geometry.Manifold.DiffFormBundle    -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.MExtDerivCoord     -- mextDerivFun, formInCoord
import Library.Geometry.Manifold.MExtDeriv          -- contMDiff_mextDerivFun (smoothness)

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.MExtDeriv

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
  contMDiff_toFun := contMDiff_mextDerivFun I φ

end Problems.Geometry.stokes_dd_zero
