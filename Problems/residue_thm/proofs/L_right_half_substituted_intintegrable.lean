import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- right_half_substituted_intintegrable: IntervalIntegrable on [1/2,1] via continuity of
-- Q∘β'∘(2·−1) (analytic Q avoids a) and derivWithin β' composed with the linear reparametrisation
-- entry_kind: Builder
theorem right_half_substituted_intintegrable
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    IntervalIntegrable
      (fun t : ℝ => Q (β' (2*t - 1)) * (2 * derivWithin β' (Set.Icc 0 1) (2*t - 1)))
      MeasureTheory.volume (1/2) 1 := by
  have hle : (1:ℝ)/2 ≤ 1 := by norm_num
  apply ContinuousOn.intervalIntegrable_of_Icc hle
  have hmap : Set.MapsTo (fun t : ℝ => 2*t - 1) (Set.Icc (1/2) 1) (Set.Icc 0 1) := by
    intro t ht; constructor <;> [linarith [ht.1]; linarith [ht.2]]
  have hlin : ContinuousOn (fun t : ℝ => 2*t - 1) (Set.Icc (1/2) 1) :=
    ((continuous_const.mul continuous_id').sub continuous_const).continuousOn
  have hβ'_cont : ContinuousOn β' (Set.Icc 0 1) := hβ'.continuousOn
  have hβ'_dw : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hβ'_avoids : Set.MapsTo (fun t : ℝ => β' (2*t - 1)) (Set.Icc (1/2) 1)
      (Set.univ \ {a}) := by
    intro t ht
    simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and]
    exact hβ'_avoid (2*t - 1) (hmap ht)
  apply ContinuousOn.mul
  · exact (hQ_an.continuousOn.comp (hβ'_cont.comp hlin hmap) hβ'_avoids)
  · exact (continuousOn_const.mul (hβ'_dw.comp hlin hmap))

end Problems.residue_thm