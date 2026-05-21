import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- int_two_alpha_eq_alpha: change of variables t ↦ 2t on [0,1/2] via integral_const_mul +
-- smul_integral_comp_mul_left, converting ∫₀^{1/2} 2·Q(α'(2t))·α''(2t) dt to ∫₀^1 Q(α'·)·α'' du
-- entry_kind: Builder
theorem int_two_alpha_eq_alpha
    {Q : ℂ → ℂ} {α' h : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1 / 2), h t = α' (2 * t)) :
    (∫ t in (0:ℝ)..(1/2:ℝ), 2 * (Q (α' (2*t)) * deriv α' (2*t))) =
      (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) := by
  calc ∫ t in (0:ℝ)..(1/2:ℝ), 2 * (Q (α' (2*t)) * deriv α' (2*t))
      = 2 * ∫ t in (0:ℝ)..(1/2:ℝ), Q (α' (2*t)) * deriv α' (2*t) :=
        intervalIntegral.integral_const_mul 2 _
    _ = ∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t := by
        rw [show (2:ℂ) = ((2:ℝ):ℂ) from by norm_cast, ← Complex.real_smul]
        have hkey := intervalIntegral.smul_integral_comp_mul_left
          (fun t => Q (α' t) * deriv α' t) (2:ℝ) (a := 0) (b := 1/2)
        simp only [mul_zero, show (2:ℝ) * (1/2:ℝ) = 1 from by norm_num] at hkey
        exact hkey

end Problems.residue_thm