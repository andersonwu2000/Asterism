import Library.Geometry.Manifold.DiffFormBundle   -- DiffForm, formBundleCore, instForm*
import Mathlib.Analysis.Calculus.DifferentialForm.Basic

/-!
# Exterior derivative restricted to a set

Smoothness and local-invariance results for `extDerivWithin`, the exterior derivative of a
differential form restricted to a set in a normed space.

## Main statements

- `extDerivWithin_contDiffOn`: `extDerivWithin form s` is `C^∞` on `s` when `form` is.
- `extDerivWithin_eq_of_mem_nhdsWithin`: the restricted exterior derivative is unchanged when
  the domain is replaced by any set that is a neighbourhood within the original domain.
-/

set_option maxHeartbeats 800000
set_option synthInstance.maxHeartbeats 400000

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.ExtDerivWithin

variable {E F : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    [NormedAddCommGroup F] [NormedSpace ℝ F]
    {n : ℕ} {form : E → E [⋀^Fin n]→L[ℝ] F}

/-- `extDerivWithin form s` is `C^∞` on `s` whenever `form` is `C^∞` on `s`
and `s` satisfies the unique differentiability condition. -/
theorem extDerivWithin_contDiffOn {s : Set E}
    (hform : ContDiffOn ℝ ∞ form s) (hs : UniqueDiffOn ℝ s) :
    ContDiffOn ℝ ∞ (extDerivWithin form s) s := by
  have h_fderiv : ContDiffOn ℝ ∞ (fderivWithin ℝ form s) s :=
    hform.fderivWithin hs (by simp)
  have h_eq : extDerivWithin form s =
      ⇑(ContinuousAlternatingMap.alternatizeUncurryFinCLM ℝ E F) ∘ fderivWithin ℝ form s := by
    funext x
    simp [extDerivWithin, ContinuousAlternatingMap.alternatizeUncurryFinCLM_apply,
      Function.comp]
  rw [h_eq]
  exact (ContinuousAlternatingMap.alternatizeUncurryFinCLM ℝ E F).contDiff.comp_contDiffOn
    h_fderiv

/-- The restricted exterior derivative at a point `y` is the same for any two sets when `t`
is a neighbourhood of `y` within `s`, provided `form` is differentiable within `t` at `y`. -/
theorem extDerivWithin_eq_of_mem_nhdsWithin {s t : Set E} {y : E}
    (hst : t ∈ nhdsWithin y s) (hs : UniqueDiffWithinAt ℝ s y)
    (hform : DifferentiableWithinAt ℝ form t y) :
    extDerivWithin form s y = extDerivWithin form t y := by
  simp only [extDerivWithin]
  congr 1
  exact fderivWithin_of_mem_nhdsWithin hst hs hform

end Library.Geometry.Manifold.ExtDerivWithin
