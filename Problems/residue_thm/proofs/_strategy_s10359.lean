import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_clean_g_section_tau_dw_eq_fderiv_apply
import Problems.residue_thm.proofs.L_section_t_dw_eq_joint_fderiv_apply

namespace Problems.residue_thm

-- Bridge the LHS to a cleaned variant whose τ'-integrand is `f (H τ' t) * fderivWithin H_joint
-- (Icc×Icc) (τ', t) (0, 1)` via a t-direction "section derivWithin = fderiv-apply" identity
-- (h_bridge), then close the τ-derivWithin via a section-chain-rule on the cleaned C¹ function
-- (h_clean). The combinator is `derivWithin_congr` (EqOn on Icc 0 1 of the τ' integrand).
theorem s10359
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      derivWithin (fun τ' => f (H τ' t) * derivWithin (H τ') (Set.Icc (0:ℝ) 1) t)
        (Set.Icc (0:ℝ) 1) τ =
      fderivWithin ℝ
        (fun p : ℝ × ℝ =>
          f (H p.1 p.2) *
            fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) ((1:ℝ), (0:ℝ))  := by
  intro τ hτ t ht
  have hmem_τ : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have h_bridge := section_t_dw_eq_joint_fderiv_apply hV hf hH hHV hH0 hH1
  have h_clean := clean_g_section_tau_dw_eq_fderiv_apply hV hf hH hHV hH0 hH1
  have heq : Set.EqOn
      (fun τ' => f (H τ' t) * derivWithin (H τ') (Set.Icc (0:ℝ) 1) t)
      (fun τ' => f (H τ' t) * fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1) := by
    intro τ' hτ'
    simp [h_bridge τ' hτ' t ht]
  rw [derivWithin_congr heq (heq hmem_τ)]
  exact h_clean τ hτ t ht

end Problems.residue_thm
