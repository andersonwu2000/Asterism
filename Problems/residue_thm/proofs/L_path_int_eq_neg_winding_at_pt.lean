import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_winding_integral_formula

namespace Problems.residue_thm

-- path_int_eq_neg_winding_at_pt: sign-flip of winding_integral_formula;
-- rewrite integrand via deriv γ t / (z - γ t) = -(deriv γ t / (γ t - z)) by ring,
-- pull negation out of integral, then substitute winding_integral_formula.
theorem path_int_eq_neg_winding_at_pt
    {γ : ℝ → ℂ} {z : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ z) :
    (∫ t in (0:ℝ)..1, deriv γ t / (z - γ t))
      = -(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ z : ℂ) := by
  have hform := winding_integral_formula hγ h_avoid hclosed
  have heq : ∀ t : ℝ, deriv γ t / (z - γ t) = -(deriv γ t / (γ t - z)) := fun t => by
    rw [show z - γ t = -(γ t - z) from by ring, div_neg]
  simp_rw [heq]
  rw [intervalIntegral.integral_neg, hform]
  ring

end Problems.residue_thm

