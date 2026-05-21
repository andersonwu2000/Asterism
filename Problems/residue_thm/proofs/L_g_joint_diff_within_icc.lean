import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- g_joint_diff_within_icc: DifferentiableWithinAt for f(H p)*fderivWithin H (0,1) on Icc×Icc,
-- by showing ContDiffOn ℝ 1 of the product (C¹ composition + C¹ fderivWithin from C² hH).
theorem g_joint_diff_within_icc
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      DifferentiableWithinAt ℝ
        (fun p : ℝ × ℝ =>
          f (H p.1 p.2) *
            fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) := by
  intro τ hτ t ht
  have hmem : (τ, t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 :=
    ⟨Set.Ico_subset_Icc_self hτ, ht⟩
  have huniq : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    uniqueDiffOn_Icc_zero_one.prod uniqueDiffOn_Icc_zero_one
  have hfR : ContDiffOn ℝ 1 f V :=
    set_option backward.isDefEq.respectTransparency false in
    (hf.contDiffOn_of_completeSpace (n := 1)).restrict_scalars ℝ
  have hH1' : ContDiffOn ℝ 1 (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) := hH.of_le (by norm_num)
  have hfact1 : ContDiffOn ℝ 1 (fun p : ℝ × ℝ => f (H p.1 p.2))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    hfR.comp hH1' (fun p hp => hHV p.1 hp.1 p.2 hp.2)
  have hfact2 : ContDiffOn ℝ 1 (fun p : ℝ × ℝ =>
      fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    (hH.fderivWithin huniq (by norm_num)).clm_apply contDiffOn_const
  exact (hfact1.mul hfact2).differentiableOn (by norm_num) (τ, t) hmem

end Problems.residue_thm
