import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_tau_deriv_eq_dw_on_ioo_prod
import Problems.residue_thm.proofs.L_tau_dw_bound_on_icc_prod

namespace Problems.residue_thm

-- Split the Ioo×Ioo τ-derivative bound into (a) a bound on the closed product
-- Icc×Icc stated with `derivWithin` (continuous on the compact, hence bounded),
-- and (b) the pointwise identification of `deriv` with `derivWithin` on the
-- interior. Combinator: M from (a), rewrite via (b) on Ioo×Ioo ⊆ Icc×Icc.
theorem s10343
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∃ M : ℝ, ∀ t ∈ Set.Ioo (0:ℝ) 1, ∀ x ∈ Set.Ioo (0:ℝ) 1,
      ‖deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) x‖ ≤ M  := by
  have h_bound := tau_dw_bound_on_icc_prod hV hf hH hHV hH0 hH1
  have h_eq := tau_deriv_eq_dw_on_ioo_prod hV hf hH hHV hH0 hH1
  obtain ⟨M, hM⟩ := h_bound
  refine ⟨M, fun t ht x hx => ?_⟩
  rw [h_eq t ht x hx]
  exact hM t (Set.Ioo_subset_Icc_self ht) x (Set.Ioo_subset_Icc_self hx)

end Problems.residue_thm
