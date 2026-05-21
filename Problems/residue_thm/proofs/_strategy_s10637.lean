import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chain_rule_at_boundary_image
import Problems.residue_thm.proofs.L_gamma_diff_at_interior

namespace Problems.residue_thm

-- Decomposition: split t ∈ Ioo 0 1 by whether φ t is in the open interior
-- Ioo 0 1 or hits an endpoint {0, 1} (since hφrange + hφmono only force
-- φ t ∈ Icc 0 1 with φ non-decreasing; interior t may map to a boundary).
--   • Interior case: extract DifferentiableAt γ (φ t) from ContDiffOn-Icc
--     via Icc_mem_nhds (sub-goal `gamma_diff_at_interior`), then the
--     standard chain rule `HasDerivAt.scomp` closes the equation.
--   • Boundary case: dispatch to sub-goal `chain_rule_at_boundary_image`,
--     where deriv φ t = 0 follows from monotonicity collapsing φ to a
--     constant on a one-sided neighborhood and a Lipschitz bound on γ
--     forces deriv (γ ∘ φ) t = 0 as well.
theorem s10637
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    ∀ t ∈ Set.Ioo (0:ℝ) 1,
      deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t)  := by
  intro t ht
  have ht_icc : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hφt_icc : φ t ∈ Set.Icc (0:ℝ) 1 := hφrange t ht_icc
  by_cases hφt_int : φ t ∈ Set.Ioo (0:ℝ) 1
  · have hφdAt : HasDerivAt φ (deriv φ t) t :=
      hφ.differentiable_one.differentiableAt.hasDerivAt
    have h_gamma_diff_int : DifferentiableAt ℝ γ (φ t) :=
      gamma_diff_at_interior hγ hφt_int
    have hγdAt : HasDerivAt γ (deriv γ (φ t)) (φ t) := h_gamma_diff_int.hasDerivAt
    exact (hγdAt.scomp t hφdAt).deriv
  · have hbnd : φ t = 0 ∨ φ t = 1 := by
      rcases hφt_icc with ⟨h0, h1⟩
      rcases eq_or_lt_of_le h0 with h0 | h0
      · exact Or.inl h0.symm
      · rcases eq_or_lt_of_le h1 with h1 | h1
        · exact Or.inr h1
        · exact absurd ⟨h0, h1⟩ hφt_int
    have h_boundary_eq : deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t) :=
      chain_rule_at_boundary_image hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono ht hbnd
    exact h_boundary_eq

end Problems.residue_thm
