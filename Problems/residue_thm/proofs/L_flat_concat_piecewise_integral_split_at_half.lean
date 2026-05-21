import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- flat_concat_piecewise_integral_split_at_half: interval additivity at midpoint 1/2
-- The piecewise integrand is ContinuousOn [0,1/2] (alpha-branch) and a.e.-equal to a
-- continuous function on [1/2,t] (beta-branch on the open Ioc); IntervalIntegrable follows
-- from ContinuousOn.intervalIntegrable + congr_ae, then
-- intervalIntegral.integral_add_adjacent_intervals closes the goal.
theorem flat_concat_piecewise_integral_split_at_half
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
      (∫ s in (0:ℝ)..t,
        (if s ≤ (1:ℝ)/2
          then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = (∫ s in (0:ℝ)..((1:ℝ)/2),
            (if s ≤ (1:ℝ)/2
              then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
              else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
          + (∫ s in ((1:ℝ)/2:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) := by
  intro t ht
  set f : ℝ → ℂ := fun s =>
    if s ≤ (1:ℝ)/2 then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                    else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)
  have hcα : ContinuousOn (fun s => (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s))
      (Set.Icc 0 (1/2)) :=
    continuousOn_const.mul
      ((hα'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl).comp
        (continuousOn_const.mul continuousOn_id)
        (fun s hs => ⟨by linarith [hs.1], by linarith [hs.2]⟩))
  have hcβ : ContinuousOn (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      (Set.Icc (1/2) 1) :=
    continuousOn_const.mul
      ((hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl).comp
        ((continuousOn_const.mul continuousOn_id).sub continuousOn_const)
        (fun s hs => ⟨by linarith [hs.1], by linarith [hs.2]⟩))
  have hfi_left : IntervalIntegrable f MeasureTheory.volume 0 (1/2) := by
    apply ContinuousOn.intervalIntegrable
    rw [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1/2)]
    exact hcα.congr fun s hs => by
      simp only [Set.mem_Icc] at hs
      simp only [f, if_pos hs.2]
  have hfi_right : IntervalIntegrable f MeasureTheory.volume (1/2) t := by
    have hβ_int : IntervalIntegrable (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2*s-1))
        MeasureTheory.volume (1/2) t := by
      apply ContinuousOn.intervalIntegrable
      rw [Set.uIcc_of_le ht.1]
      exact hcβ.mono (Set.Icc_subset_Icc_right ht.2)
    apply hβ_int.congr_ae
    rw [Set.uIoc_of_le ht.1]
    filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioc] with s hs
    simp only [Set.mem_Ioc] at hs
    simp only [f, if_neg (show ¬ s ≤ (1:ℝ)/2 from by linarith [hs.1])]
  symm
  exact intervalIntegral.integral_add_adjacent_intervals hfi_left hfi_right

end Problems.residue_thm
