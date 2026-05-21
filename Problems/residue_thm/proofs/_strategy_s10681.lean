import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct proof: pointwise rewrite a*(2*b) = 2 • (a*b), pull const out via integral_smul,
-- then apply intervalIntegral.smul_integral_comp_mul_sub with (a:=1/2,b:=1,c:=2,d:=1).
theorem s10681
    {Q : ℂ → ℂ} {β' : ℝ → ℂ} :
    (∫ t in ((1/2) : ℝ)..1, Q (β' (2*t - 1)) * (2 * deriv β' (2*t - 1))) =
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t)  := by
  have h := intervalIntegral.smul_integral_comp_mul_sub
    (a := (1/2 : ℝ)) (b := (1 : ℝ)) (fun u => Q (β' u) * deriv β' u) 2 1
  simp only [show (2:ℝ) * (1/2) - 1 = 0 from by norm_num,
             show (2:ℝ) * 1 - 1 = 1 from by norm_num] at h
  have hcongr : (∫ t in ((1/2) : ℝ)..1, Q (β' (2*t - 1)) * (2 * deriv β' (2*t - 1))) =
                ∫ t in ((1/2) : ℝ)..1, (2 : ℂ) • (Q (β' (2*t - 1)) * deriv β' (2*t - 1)) := by
    refine intervalIntegral.integral_congr ?_
    intro t _
    simp only [smul_eq_mul]
    ring
  rw [hcongr]
  rw [intervalIntegral.integral_smul]
  exact h

end Problems.residue_thm
