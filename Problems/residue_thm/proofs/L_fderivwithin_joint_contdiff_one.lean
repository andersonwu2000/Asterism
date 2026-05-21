import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- fderivwithin_joint_contdiff_one: C¹ regularity of fderivWithin H·S evaluated at (0,1),
-- via ContDiffOn.fderivWithin (C² → C¹ within-deriv on unique-diff product Icc×Icc)
-- followed by ContDiffOn.clm_apply at the constant vector (0,1).
-- entry_kind: Builder
theorem fderivwithin_joint_contdiff_one
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ContDiffOn ℝ 1
      (fun p : ℝ × ℝ =>
        fderivWithin ℝ (fun q : ℝ × ℝ => H q.1 q.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) p ((0:ℝ), (1:ℝ)))
    (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) := by
  have hUD : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    UniqueDiffOn.prod uniqueDiffOn_Icc_zero_one uniqueDiffOn_Icc_zero_one
  exact (hH.fderivWithin hUD (by norm_num)).clm_apply contDiffOn_const

end Problems.residue_thm
