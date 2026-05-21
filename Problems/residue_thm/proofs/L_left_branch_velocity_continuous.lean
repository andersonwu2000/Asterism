import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- left_branch_velocity_continuous: continuity of s ↦ 2·derivWithin α' (Icc 0 1) (2s) on Icc 0 (1/2)
-- via ContDiffOn.continuousOn_derivWithin composed with the linear map s ↦ 2s
theorem left_branch_velocity_continuous
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContinuousOn (fun s : ℝ => 2 * derivWithin α' (Set.Icc 0 1) (2*s))
      (Set.Icc 0 ((1:ℝ)/2)) := by
  have hcont : ContinuousOn (derivWithin α' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hα'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hmaps : Set.MapsTo (fun s : ℝ => 2 * s) (Set.Icc 0 (1/2)) (Set.Icc 0 1) := by
    intro s hs
    constructor
    · linarith [hs.1]
    · linarith [hs.2]
  exact continuousOn_const.mul
    (hcont.comp ((continuous_const.mul continuous_id).continuousOn) hmaps)

end Problems.residue_thm
