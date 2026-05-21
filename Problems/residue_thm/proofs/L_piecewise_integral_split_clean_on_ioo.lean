import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

set_option linter.style.emptyLine false


-- entry_kind: Builder
-- piecewise_integral_split_clean_on_ioo: split piecewise integral at midpoint 1/2
-- via integral_add_adjacent_intervals, simplify branches; second branch uses congr_ae
-- to handle the endpoint s=1/2 where the if-branch is true but measure-zero
theorem piecewise_integral_split_clean_on_ioo
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ∀ u ∈ Set.Ioo ((1:ℝ)/2) 1,
      (∫ s in (0:ℝ)..u,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = (∫ s in (0:ℝ)..((1:ℝ)/2), 2 * derivWithin α' (Set.Icc 0 1) (2*s))
          + ∫ s in ((1:ℝ)/2)..u, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1) := by
  intro u hu
  have h0h : (0:ℝ) ≤ 1/2 := by norm_num
  have hhu : (1:ℝ)/2 ≤ u := hu.1.le
  have hα'dw : ContinuousOn (derivWithin α' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hα'.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl
  have hβ'dw : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hβ'.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl
  have hα_cont : ContinuousOn (fun s => (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s))
      (Set.Icc 0 (1/2)) := by
    apply ContinuousOn.mul continuousOn_const
    apply ContinuousOn.comp hα'dw
    · exact (continuous_const.mul continuous_id).continuousOn
    · intro s hs; exact ⟨by linarith [hs.1], by linarith [hs.2]⟩
  have hβ_cont : ContinuousOn (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      (Set.Icc (1/2) u) := by
    apply ContinuousOn.mul continuousOn_const
    apply ContinuousOn.comp hβ'dw
    · exact ((continuous_const.mul continuous_id).sub continuous_const).continuousOn
    · intro s hs; exact ⟨by linarith [hs.1], by linarith [hs.2, hu.2]⟩
  have hα_intbl : IntervalIntegrable (fun s => (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s))
      MeasureTheory.volume 0 (1/2) :=
    hα_cont.intervalIntegrable_of_Icc h0h
  have hβ_intbl : IntervalIntegrable (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      MeasureTheory.volume (1/2) u :=
    hβ_cont.intervalIntegrable_of_Icc hhu

  have hpw_int1 : IntervalIntegrable
      (fun s => if s ≤ (1:ℝ)/2 then (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      MeasureTheory.volume 0 (1/2) := by
    rw [intervalIntegrable_iff, Set.uIoc_of_le h0h]
    apply (hα_intbl.1).congr_fun _ measurableSet_Ioc
    intro s hs
    change (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s) =
        if s ≤ 1/2 then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1)

    rw [if_pos hs.2]
  have hpw_int2 : IntervalIntegrable
      (fun s => if s ≤ (1:ℝ)/2 then (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      MeasureTheory.volume (1/2) u := by
    rw [intervalIntegrable_iff, Set.uIoc_of_le hhu]
    apply (hβ_intbl.1).congr_fun _ measurableSet_Ioc
    intro s hs
    change (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1) =
        if s ≤ 1/2 then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1)

    rw [if_neg (not_le.mpr hs.1)]
  rw [← intervalIntegral.integral_add_adjacent_intervals hpw_int1 hpw_int2]
  congr 1
  · apply intervalIntegral.integral_congr
    intro s hs
    rw [Set.uIcc_of_le h0h] at hs
    change (if s ≤ 1/2 then (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1)) =
        2 * derivWithin α' (Set.Icc 0 1) (2 * s)
    rw [if_pos hs.2]

  · apply intervalIntegral.integral_congr_ae
    rw [Set.uIoc_of_le hhu]
    apply MeasureTheory.ae_of_all MeasureTheory.volume
    intro s hs
    rw [if_neg (not_le.mpr hs.1)]

end Problems.residue_thm
