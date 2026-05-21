import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_h_deriv_exp_dw
import Problems.residue_thm.proofs.L_h_deriv_gamma_sub_dw
import Problems.residue_thm.proofs.L_value_dw_eq_target

namespace Problems.residue_thm

-- Product-rule decomposition with `derivWithin γ (Icc 0 1) s` as the intermediate
-- derivative value for both factors, avoiding the dead-strategy s10307 issue where
-- `deriv γ 0` is junk (since `Icc 0 1 ∉ nhds 0`, `DifferentiableAt ℝ γ 0` is not
-- implied by `ContDiffOn ℝ 1 γ (Icc 0 1)`); then a single algebraic equality
-- (`value_dw_eq_target`, both sides = 0 since `γ s - a ≠ 0`) transports the
-- product-rule output to the parent's `deriv γ s` shape.
theorem s10311
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a))
        (-(deriv γ s / (γ s - a)) *
           Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a) +
         Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * deriv γ s)
        (Set.Icc (0:ℝ) 1) s  := by
  intro s hs
  have h_exp := h_deriv_exp_dw hγ hclosed havoid s hs
  have h_gamma := h_deriv_gamma_sub_dw hγ hclosed havoid s hs
  have h_value_eq := value_dw_eq_target hγ hclosed havoid s hs
  have h_combined := h_exp.mul h_gamma
  rw [h_value_eq] at h_combined
  exact h_combined

end Problems.residue_thm
