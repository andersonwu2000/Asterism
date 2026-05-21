import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_integrand_intvl_integrable
import Problems.residue_thm.proofs.L_residue_kernel_intvl_integrable

namespace Problems.residue_thm

-- Pointwise distribute `(P (γ t) - r/(γ t - a)) * γ'(t)` and split the integral by linearity.
-- (a) path_integrand_intvl_integrable: `t ↦ P (γ t) * deriv γ t` is interval-integrable on [0,1].
-- (b) residue_kernel_intvl_integrable: `t ↦ deriv γ t / (γ t - a)` is interval-integrable on [0,1].
-- Combine via `intervalIntegral.integral_congr` (ring identity), then `integral_sub` to peel off
-- the second integrand, then `integral_const_mul` pulls the residue scalar out.
theorem s10484
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, (P (γ t) - Complex.residue P a / (γ t - a)) * deriv γ t) =
      (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) -
        Complex.residue P a * (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a))  := by
  set r := Complex.residue P a with hr_def
  have hA : IntervalIntegrable (fun t => P (γ t) * deriv γ t) MeasureTheory.volume 0 1 :=
    path_integrand_intvl_integrable hP hγ h_avoid
  have hB : IntervalIntegrable (fun t => deriv γ t / (γ t - a)) MeasureTheory.volume 0 1 :=
    residue_kernel_intvl_integrable hγ h_avoid
  have hB' : IntervalIntegrable (fun t => r * (deriv γ t / (γ t - a))) MeasureTheory.volume 0 1 :=
    hB.const_mul r
  have heq : ∀ t ∈ Set.uIcc (0:ℝ) 1,
      (P (γ t) - r / (γ t - a)) * deriv γ t =
      P (γ t) * deriv γ t - r * (deriv γ t / (γ t - a)) := by
    intro t _; ring
  rw [intervalIntegral.integral_congr heq]
  rw [intervalIntegral.integral_sub hA hB']
  congr 1
  exact intervalIntegral.integral_const_mul r (fun t => deriv γ t / (γ t - a))

end Problems.residue_thm
