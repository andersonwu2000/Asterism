import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_partial_tau_eq_fderiv_apply

namespace Problems.residue_thm

-- Decomposition: rewrite the τ-section derivWithin as the (1,0)-application of the joint
-- fderivWithin, then leverage joint continuity of `fderivWithin` (from C² of the uncurried H).
-- Sub-goal `partial_tau_eq_fderiv_apply` is a pointwise derivative identity (Builder).
-- Joint fderivWithin continuity is a one-liner via `ContDiffOn.continuousOn_fderivWithin`,
-- composed with the τ-slice map and CLM evaluation at (1,0).
theorem s10344
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1,
      ContinuousOn
        (fun t => derivWithin (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) τ)
        (Set.Icc (0:ℝ) 1) := by
  intro τ hτ
  have hτ' : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have h_eq : ∀ t ∈ Set.Icc (0:ℝ) 1,
      derivWithin (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) τ =
      fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) (1, 0) :=
    fun t ht => partial_tau_eq_fderiv_apply hV hf hH hHV hH0 hH1 τ hτ t ht

  have h_uniq : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    uniqueDiffOn_Icc_zero_one.prod uniqueDiffOn_Icc_zero_one
  have h_joint : ContinuousOn (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    hH.continuousOn_fderivWithin h_uniq (by norm_num)
  have h_slice : ContinuousOn (fun t => fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) (Set.Icc (0:ℝ) 1) :=
    h_joint.comp (continuous_const.prodMk continuous_id).continuousOn
      (fun t ht => Set.mk_mem_prod hτ' ht)
  have h_apply : ContinuousOn (fun t => fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) (1, 0)) (Set.Icc (0:ℝ) 1) :=
    (ContinuousLinearMap.apply ℝ ℂ (1, 0)).continuous.comp_continuousOn h_slice
  exact h_apply.congr (fun t ht => h_eq t ht)



end Problems.residue_thm
