import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- concat_velocity_if_eq_left_on_prefix: intervalIntegral.integral_congr collapses the
-- if-branch to the left summand, since every s ∈ [[0,t]] with t ≤ 1/2 satisfies s ≤ 1/2.
theorem concat_velocity_if_eq_left_on_prefix
    {α' β' : ℝ → ℂ}
    {t : ℝ} (ht : t ∈ Set.Icc (0 : ℝ) (1 / 2)) :
    (∫ s in (0 : ℝ)..t,
        (if s ≤ (1 : ℝ) / 2
          then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1))) =
    (∫ s in (0 : ℝ)..t, 2 * derivWithin α' (Set.Icc 0 1) (2 * s)) := by
  apply intervalIntegral.integral_congr
  intro s hs
  simp only [Set.uIcc_of_le ht.1] at hs
  have hs_le : s ≤ 1 / 2 := le_trans hs.2 ht.2
  simp only [if_pos hs_le]

end Problems.residue_thm
