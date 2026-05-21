import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- integral_one_sub_substitution: substitution u = 1-t via integral_comp_sub_left
theorem integral_one_sub_substitution
    {Q : ℂ → ℂ} {a : ℂ} {β : ℝ → ℂ}
    (_hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (_hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
    (∫ t in (0 : ℝ)..1, Q (β (1 - t)) * deriv β (1 - t)) =
      ∫ u in (0 : ℝ)..1, Q (β u) * deriv β u := by
  have h := intervalIntegral.integral_comp_sub_left
    (fun u => Q (β u) * deriv β u) (a := (0:ℝ)) (b := 1) 1
  simp only [show (1:ℝ) - 1 = 0 from by norm_num,
             show (1:ℝ) - 0 = 1 from by norm_num] at h
  exact h

end Problems.residue_thm
