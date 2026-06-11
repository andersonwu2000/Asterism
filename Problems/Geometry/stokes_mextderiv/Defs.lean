/-
  Defs.lean — PARKED (not yet buildable). Owns `formInCoord` (coordinate rep of a
  form via the bundle trivialisation) and `mextDerivFun` (the raw section function of
  the exterior derivative: chart-transport of mathlib's normed-space `extDerivWithin`).
  Cites P4 (`stokes_form_bundle`) for `DiffForm` / `formBundleCore` / the bundle
  instances. The Root proves `mextDerivFun` is a `C^∞` section (the smoothness witness
  that lets P6 assemble `mextDeriv : DiffForm I M (k+1)`).

  ⚠️ FINALIZE AFTER P4 MIGRATES: import + open of P4's Library module (TBD name,
  holds `DiffForm`, `formBundleCore`, `instFormFiberBundle`, `instFormVectorBundle`),
  and confirm the `CMDiff`/`T%` smoothness statement form (needs the fibre-bundle
  instances in scope — the reason this is a standalone Root, see §A.5 note).
-/
import Mathlib
import Library.Geometry.Manifold.DiffFormBundle   -- DiffForm, formBundleCore, instForm*

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle

namespace Problems.Geometry.stokes_mextderiv

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- Coordinate representative of a `k`-form near `x`: read `φ` through the bundle
    trivialisation at `x`, as a function `E → (E[⋀^k]→L ℝ)`. -/
noncomputable def formInCoord {k : ℕ} (φ : DiffForm I M k) (x : M) :
    E → (E [⋀^Fin k]→L[ℝ] ℝ) :=
  fun y =>
    let p := (extChartAt I x).symm y
    Trivialization.continuousLinearMapAt ℝ
      (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x) p (φ p)

/-- Raw section function of the exterior derivative: apply the model `extDerivWithin`
    on `range I` to the coordinate rep, transport back into the `(k+1)`-fibre. -/
noncomputable def mextDerivFun {k : ℕ} (φ : DiffForm I M k) (x : M) :
    (formBundleCore (M := M) I (k + 1)).Fiber x :=
  Trivialization.symmL ℝ
    (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ) (formBundleCore (M := M) I (k + 1)).Fiber x) x
    (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))

/-- Smooth-vector-bundle instance for `⋀ᵏ T*M`, from the cited `formBundleCore_isContMDiff`
    (P4). Needed so the section-smoothness statement (the Root's `CMDiff`/`T%`) has the
    smooth bundle structure + fibre-bundle instance in scope. -/
noncomputable instance instFormBundleContMDiff (k : ℕ) :
    ContMDiffVectorBundle ∞ (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber I := by
  haveI := formBundleCore_isContMDiff (M := M) I k
  exact (formBundleCore (M := M) I k).instContMDiffVectorBundle

end Problems.Geometry.stokes_mextderiv
