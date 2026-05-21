import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- split_at_half_wrap: integral split at midpoint via integral_add_adjacent_intervals
-- On each half, the piecewise integrand agrees pointwise with a continuous branch.
theorem split_at_half_wrap
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
  symm
  apply intervalIntegral.integral_add_adjacent_intervals
  · -- IntervalIntegrable on [0, 1/2]: piecewise = first branch everywhere
    apply ContinuousOn.intervalIntegrable_of_Icc (by norm_num)
    have hα'_cont : ContinuousOn (derivWithin α' (Set.Icc 0 1)) (Set.Icc 0 1) :=
      hα'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
    have h_map1 : Set.MapsTo (fun s : ℝ => 2 * s) (Set.Icc 0 (1/2)) (Set.Icc 0 1) :=
      fun s hs => ⟨by linarith [hs.1], by linarith [hs.2]⟩
    have hbranch1 : ContinuousOn (fun s => (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s))
        (Set.Icc 0 (1/2)) :=
      (hα'_cont.comp (continuous_const.mul continuous_id).continuousOn h_map1).const_mul 2
    apply hbranch1.congr
    intro s hs
    dsimp only
    exact if_pos hs.2
  · -- IntervalIntegrable on [1/2, t]: piecewise matches second branch (or 0 at boundary)
    apply ContinuousOn.intervalIntegrable_of_Icc ht.1
    have hβ'_cont : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
      hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
    have h_map2 : Set.MapsTo (fun s : ℝ => 2 * s - 1) (Set.Icc (1/2) t) (Set.Icc 0 1) :=
      fun s hs => ⟨by linarith [hs.1], by linarith [hs.2, ht.2]⟩
    have hbranch2 : ContinuousOn (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
        (Set.Icc (1/2) t) :=
      (hβ'_cont.comp ((continuous_const.mul continuous_id).sub continuous_const).continuousOn
        h_map2).const_mul 2
    apply hbranch2.congr
    intro s hs
    dsimp only
    by_cases heq : s = (1:ℝ)/2
    · subst heq
      simp only [le_refl, ↓reduceIte]
      rw [show (2:ℝ) * (1/2 : ℝ) - 1 = 0 from by norm_num,
          show (2:ℝ) * (1/2 : ℝ) = 1 from by norm_num,
          hβ'_deriv, hα'_deriv, mul_zero]
    · have hlt : (1:ℝ)/2 < s := lt_of_le_of_ne hs.1 (Ne.symm heq)
      rw [if_neg (not_le.mpr hlt)]

end Problems.residue_thm
