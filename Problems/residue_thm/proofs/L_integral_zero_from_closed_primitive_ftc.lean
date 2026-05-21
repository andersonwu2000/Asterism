import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- integral_zero_from_closed_primitive_ftc: FTC collapses ∫g·γ' to F 1 - F 0 = 0 via closed path
theorem integral_zero_from_closed_primitive_ftc
    {g : ℂ → ℂ} {γ : ℝ → ℂ} {F : ℝ → ℂ}
    (hF_cont : ContinuousOn F (Set.Icc (0 : ℝ) 1))
    (hF_deriv : ∀ t ∈ Set.Ioo (0 : ℝ) 1, HasDerivAt F (g (γ t) * deriv γ t) t)
    (hF_closed : F 0 = F 1)
    (hint : IntervalIntegrable (fun t => g (γ t) * deriv γ t)
              MeasureTheory.volume 0 1) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 := by
  rw [intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le zero_le_one hF_cont hF_deriv hint,
      ← hF_closed, sub_self]

end Problems.residue_thm
