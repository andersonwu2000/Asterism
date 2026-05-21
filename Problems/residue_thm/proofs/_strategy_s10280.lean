import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_exp_winding_integral_eq_one

namespace Problems.residue_thm

-- Convert the integrality ∃ k, I = 2πi·k into the equivalent exponential
-- equation `exp(I) = 1`, then extract the integer via `Complex.exp_eq_one_iff`.
-- The exp-form sub-goal isolates the analytic content (ODE/derivative argument
-- on (γ - a)·exp(-G) where G is the antiderivative of deriv γ / (γ - a)), while
-- the integer extraction here is a one-line Mathlib lookup + ring rearrangement.
theorem s10280
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∃ k : ℤ, (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) =
      2 * Real.pi * Complex.I * k  := by
  have h_exp_one := exp_winding_integral_eq_one hU hT hγ hmap hclosed a ha
  obtain ⟨n, hn⟩ := Complex.exp_eq_one_iff.mp h_exp_one
  refine ⟨n, ?_⟩
  rw [hn]
  ring
end Problems.residue_thm
