import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chain_deriv_sum_eq_zero
import Problems.residue_thm.proofs.L_has_deriv_within_h_formula

namespace Problems.residue_thm

-- Compute `HasDerivWithinAt H (deriv-formula) (Icc 0 1) s` via product/chain/FTC
-- (`h_chain`), then reduce the formula to `0` algebraically using `γ s - a ≠ 0`
-- (`h_zero`); rewrite and convert to `derivWithin = 0` via `uniqueDiffOn_Icc_zero_one`.
theorem s10304
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      derivWithin
        (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a))
        (Set.Icc (0:ℝ) 1) s = 0  := by
  intro s hs
  have h_chain := has_deriv_within_h_formula hγ hclosed havoid s hs
  have h_zero := chain_deriv_sum_eq_zero hγ hclosed havoid s hs
  rw [h_zero] at h_chain
  exact h_chain.derivWithin (uniqueDiffOn_Icc_zero_one s (Set.Ico_subset_Icc_self hs))

end Problems.residue_thm
