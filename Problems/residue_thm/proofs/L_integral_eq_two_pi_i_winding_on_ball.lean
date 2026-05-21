import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_winding_integral_formula

namespace Problems.residue_thm

-- integral_eq_two_pi_i_winding_on_ball: wrapper for winding_integral_formula;
-- h_avoid + ball membership give γ t ≠ w for all t, then the formula applies.
theorem integral_eq_two_pi_i_winding_on_ball
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (_hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) z) :
    ∀ w ∈ Metric.ball z r,
      (∫ t in (0:ℝ)..1, deriv γ t / (γ t - w))
        = 2 * Real.pi * Complex.I * ((Complex.windingNumber γ w : ℤ) : ℂ) := by
  intro w hw
  have h_avoid_w : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ w := by
    intro t ht heq
    have hdist : r < dist (γ t) z := h_avoid t ht
    rw [heq] at hdist
    exact absurd (Metric.mem_ball.mp hw) (not_lt.mpr hdist.le)
  exact winding_integral_formula hγ h_avoid_w hclosed

end Problems.residue_thm
