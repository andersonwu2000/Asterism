import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_differentiable_exp_neg_integral
import Problems.residue_thm.proofs.L_differentiable_gamma_sub_a

namespace Problems.residue_thm

-- Split the product `exp(-G(s)) · (γ s - a)` into its two factors and combine via `.mul`.
-- Sub-goals: (1) differentiability of `s ↦ exp(-∫₀ˢ deriv γ /(γ-a))` — analytic core,
-- needs FTC + chain rule; (2) differentiability of `s ↦ γ s - a` — direct from `hγ`.
theorem s10303
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    DifferentiableOn ℝ
      (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a))
      (Set.Icc (0:ℝ) 1)  := by
  have h_exp := differentiable_exp_neg_integral hγ hclosed havoid
  have h_lin := differentiable_gamma_sub_a (a := a) hγ
  exact h_exp.mul h_lin

end Problems.residue_thm
