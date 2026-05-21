import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrating_factor_at_zero
import Problems.residue_thm.proofs.L_integrating_factor_eq_initial_value

namespace Problems.residue_thm

-- Decompose constancy of F(t) := (γ t - a) · exp(-∫₀ᵗ deriv γ s/(γ s - a)) into
-- (1) boundary value F(0) = γ 0 - a (pure algebra: ∫₀⁰ = 0, exp 0 = 1) and
-- (2) constancy F(t) = F(0) on Icc 0 1 (analytic core: product rule gives F'(t) = 0).
-- Combinator: F(t) = F(0) = γ 0 - a by trans.
theorem s10284
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ t ∈ Set.Icc (0:ℝ) 1,
      (γ t - a) * Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a)) = γ 0 - a  := by
  intro t ht
  have h_at_zero := integrating_factor_at_zero hU hT hγ hmap hclosed a ha
  have h_const := integrating_factor_eq_initial_value hU hT hγ hmap hclosed a ha t ht
  exact h_const.trans h_at_zero

end Problems.residue_thm
