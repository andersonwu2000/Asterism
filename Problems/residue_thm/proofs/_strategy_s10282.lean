import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrating_factor_constant_on_icc

namespace Problems.residue_thm

-- Reduce the endpoint identity to the abstract constancy of the integrating
-- factor F(t) = (γ t - a) · exp(-∫₀ᵗ deriv γ s / (γ s - a)) on [0,1].
-- Sub-goal `integrating_factor_constant_on_icc` is strictly stronger (∀ t)
-- and isolates the analytic content (FTC + chain rule + F'≡0 ⇒ F const).
-- Combinator: specialize at t = 1; F(0) = γ 0 - a since the integral over
-- [0,0] is 0 and exp 0 = 1, so the constancy at t = 1 is exactly our goal.
theorem s10282
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    (γ 1 - a) * Complex.exp (- ∫ t in (0:ℝ)..1, deriv γ t / (γ t - a))
      = γ 0 - a  := by
  have h_const :=
    integrating_factor_constant_on_icc hU hT hγ hmap hclosed a ha
  exact h_const 1 (Set.right_mem_Icc.mpr zero_le_one)

end Problems.residue_thm
