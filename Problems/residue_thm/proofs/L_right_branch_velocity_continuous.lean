import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- right_branch_velocity_continuous: ContinuousOn of s ↦ 2·derivWithin β' (Icc 0 1) (2s-1)
-- on Icc (1/2) 1, via ContDiffOn.continuousOn_derivWithin + affine MapsTo composition.
-- entry_kind: Builder

theorem right_branch_velocity_continuous
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContinuousOn (fun s : ℝ => 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      (Set.Icc ((1:ℝ)/2) 1) := by
    have hderiv : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
      hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one (by norm_num)
    have hmap : ContinuousOn (fun s : ℝ => 2 * s - 1) (Set.Icc ((1:ℝ)/2) 1) :=
      ((continuous_const.mul continuous_id).sub continuous_const).continuousOn
    have hmapsTo : Set.MapsTo (fun s : ℝ => 2 * s - 1) (Set.Icc ((1:ℝ)/2) 1) (Set.Icc 0 1) := by
      intro s hs
      simp only [Set.mem_Icc] at hs ⊢
      constructor <;> linarith [hs.1, hs.2]
    exact continuousOn_const.mul (hderiv.comp hmap hmapsTo)

end Problems.residue_thm
