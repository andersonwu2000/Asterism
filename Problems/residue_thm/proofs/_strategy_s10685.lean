import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_piecewise_integral_split_clean_on_ioo

namespace Problems.residue_thm

-- Strip α' 0 via add_assoc, reducing to a clean integral identity:
-- ∫ piecewise on (0,u) = ∫ alpha-branch on (0,1/2) + ∫ beta-branch on (1/2,u).
-- The sub-goal piecewise_integral_split_clean_on_ioo carries that identity.
theorem s10685
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ∀ u ∈ Set.Ioo ((1:ℝ)/2) 1,
      (α' 0 + ∫ s in (0:ℝ)..u,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = (α' 0 + ∫ s in (0:ℝ)..((1:ℝ)/2),
                  2 * derivWithin α' (Set.Icc 0 1) (2*s)) +
          ∫ s in ((1:ℝ)/2)..u, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)  := by
  intro u hu
  have h_split := piecewise_integral_split_clean_on_ioo hα' hβ' u hu
  rw [h_split, add_assoc]





end Problems.residue_thm
