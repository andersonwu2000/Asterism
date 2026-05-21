import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_hasderivwithinat_tau_section_apply_zero_one

namespace Problems.residue_thm

-- Schwarz-bridge step (B): (1,0)-direction iterated fderivWithin at (τ,t),
-- evaluated as a CLM at (0,1), equals the τ-section derivWithin of
-- `τ' ↦ (fderivWithin H (Icc×Icc) (τ', t)) (0, 1)` (lesson-34 pattern on τ-side).
-- The single sub-goal provides the `HasDerivWithinAt` for the CLM-applied section;
-- close via `HasDerivWithinAt.derivWithin` with `uniqueDiffOn_Icc_zero_one`.
theorem s10394
    {H : ℝ → ℝ → ℂ}
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      (fderivWithin ℝ (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) (1, 0) (0, 1) =
        derivWithin (fun τ' =>
            (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
                (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t)) (0, 1))
          (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ t ht
  have h_section := hasderivwithinat_tau_section_apply_zero_one hH τ hτ t ht
  exact (h_section.derivWithin (uniqueDiffOn_Icc_zero_one τ (Set.Ico_subset_Icc_self hτ))).symm

end Problems.residue_thm
