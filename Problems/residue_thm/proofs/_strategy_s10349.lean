import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_clean_g_joint_contdiff_one
import Problems.residue_thm.proofs.L_clean_tau_deriv_eq_g_joint_fderiv_apply

namespace Problems.residue_thm

-- Decompose into joint C¹ smoothness of the (τ, t)-extended integrand on `Icc×Icc`
-- (replacing the inner `derivWithin (H τ') (Icc 0 1) t` with `fderivWithin H_joint
-- (Icc×Icc) p (0,1)`) plus the pointwise identity equating the τ-section derivWithin
-- to fderivWithin in direction (1,0). Continuity of the τ-slice falls out of
-- `ContDiffOn.continuousOn_fderivWithin` composed with the τ-slice map and CLM eval.
theorem s10349
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
        (fun t => derivWithin
          (fun τ' => f (H τ' t) * derivWithin (H τ') (Set.Icc (0:ℝ) 1) t) (Set.Icc (0:ℝ) 1) τ)
        (Set.Icc (0:ℝ) 1)  := by
  intro τ hτ
  have hτ' : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have h_contdiff := clean_g_joint_contdiff_one hV hf hH hHV hH0 hH1
  have h_eq := clean_tau_deriv_eq_g_joint_fderiv_apply hV hf hH hHV hH0 hH1 τ hτ
  have h_uniq : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    uniqueDiffOn_Icc_zero_one.prod uniqueDiffOn_Icc_zero_one
  have h_fderiv_cont : ContinuousOn
      (fderivWithin ℝ
        (fun p : ℝ × ℝ =>
          f (H p.1 p.2) *
            fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    h_contdiff.continuousOn_fderivWithin h_uniq le_rfl
  have h_slice : ContinuousOn
      (fun t => fderivWithin ℝ
        (fun p : ℝ × ℝ =>
          f (H p.1 p.2) *
            fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t))
      (Set.Icc (0:ℝ) 1) :=
    h_fderiv_cont.comp (continuous_const.prodMk continuous_id).continuousOn
      (fun t ht => Set.mk_mem_prod hτ' ht)
  have h_apply : ContinuousOn
      (fun t => fderivWithin ℝ
        (fun p : ℝ × ℝ =>
          f (H p.1 p.2) *
            fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) ((1:ℝ), (0:ℝ)))
      (Set.Icc (0:ℝ) 1) :=
    (ContinuousLinearMap.apply ℝ ℂ ((1:ℝ), (0:ℝ))).continuous.comp_continuousOn h_slice
  exact h_apply.congr (fun t ht => h_eq t ht)

end Problems.residue_thm
