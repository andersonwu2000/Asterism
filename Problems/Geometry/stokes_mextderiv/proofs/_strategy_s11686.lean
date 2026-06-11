import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs

namespace Problems.Geometry.stokes_mextderiv

open scoped ContDiff

-- extDerivWithin form s = alternatizeUncurryFinCLM ∘ fderivWithin ℝ form s;
-- the CLM is C^∞ and fderivWithin of a C^∞ family is C^∞ on s (UniqueDiffOn, ∞+1 = ∞).
theorem s11686 {E F : Type*}
    [NormedAddCommGroup E] [NormedSpace ℝ E]
    [NormedAddCommGroup F] [NormedSpace ℝ F]
    {n : ℕ} {form : E → E [⋀^Fin n]→L[ℝ] F} {s : Set E}
    (hform : ContDiffOn ℝ ∞ form s) (hs : UniqueDiffOn ℝ s) :
    ContDiffOn ℝ ∞ (extDerivWithin form s) s  := by
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

end Problems.Geometry.stokes_mextderiv
