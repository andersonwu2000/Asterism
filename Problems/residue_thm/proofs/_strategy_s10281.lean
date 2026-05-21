import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_gamma_zero_minus_a_ne_zero
import Problems.residue_thm.proofs.L_integrating_factor_endpoint_eq

namespace Problems.residue_thm

-- Reduce `exp(∫ deriv γ / (γ - a)) = 1` to (i) `γ 0 - a ≠ 0` and
-- (ii) the integrating-factor endpoint identity
-- `(γ 1 - a) · exp(-∫) = γ 0 - a`, then use `γ 0 = γ 1` and cancel
-- (γ 0 - a) ≠ 0 to get `exp(-H) = 1`, and conclude via `exp H · exp(-H) = 1`.
-- Sub-goal (i) is a Builder leaf (γ 0 ∈ U \ T, a ∈ T, so γ 0 ≠ a).
-- Sub-goal (ii) isolates the analytic content (constancy of the integrating
-- factor on [0,1]) — strictly simpler than the parent because the outer
-- `Complex.exp` and the unification with `1` are stripped away.
theorem s10281
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    Complex.exp (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 1  := by
  set H := ∫ t in (0:ℝ)..1, deriv γ t / (γ t - a) with hHdef
  have hne : γ 0 - a ≠ 0 :=
    gamma_zero_minus_a_ne_zero hU hT hγ hmap hclosed a ha
  have hint : (γ 1 - a) * Complex.exp (-H) = γ 0 - a :=
    integrating_factor_endpoint_eq hU hT hγ hmap hclosed a ha
  rw [← hclosed] at hint
  have h_exp_neg : Complex.exp (-H) = 1 := by
    have hcancel : (γ 0 - a) * Complex.exp (-H) = (γ 0 - a) * 1 := by
      rw [mul_one]; exact hint
    exact mul_left_cancel₀ hne hcancel
  have hsum : Complex.exp H * Complex.exp (-H) = 1 := by
    rw [← Complex.exp_add, add_neg_cancel, Complex.exp_zero]
  rw [h_exp_neg, mul_one] at hsum
  exact hsum

end Problems.residue_thm
