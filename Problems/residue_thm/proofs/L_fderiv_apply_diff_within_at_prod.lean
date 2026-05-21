import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- fderiv_apply_diff_within_at_prod: DifferentiableWithinAt of p ↦ fderivWithin G S p v follows
-- from ContDiffOn ℝ 2 G S via ContDiffOn.fderivWithin (gives ContDiffOn ℝ 1 of fderivWithin,
-- hence DifferentiableWithinAt), then CLM evaluation at the fixed vector (0, 1).
theorem fderiv_apply_diff_within_at_prod
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      DifferentiableWithinAt ℝ
        (fun p : ℝ × ℝ =>
          fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) := by
  intro τ hτ t ht
  have hS : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)).prod (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1))
  have hmem : (τ, t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 :=
    Set.mk_mem_prod (Set.mem_Icc.mpr ⟨hτ.1, hτ.2.le⟩) (Set.mem_Icc.mpr ⟨ht.1.le, ht.2.le⟩)
  have hfD : DifferentiableWithinAt ℝ (fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
    (hH.fderivWithin (m := 1) hS (by norm_num)).differentiableOn one_ne_zero (τ, t) hmem
  exact hfD.clm_apply (differentiableWithinAt_const _)

end Problems.residue_thm
