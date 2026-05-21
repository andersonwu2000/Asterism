import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- isolating_radius_in_open_finset: for each pole a ∈ T, produce an isolating ball
-- disjoint from all other T-points, using finiteness of T and openness of U.
theorem isolating_radius_in_open_finset
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T)) :
    ∀ a ∈ T, ∃ r : ℝ, 0 < r ∧ Metric.ball a r ⊆ U ∧
      ∀ b ∈ T, b ≠ a → b ∉ Metric.ball a r := by
  intro a haT
  have haU : a ∈ U := hT a haT
  obtain ⟨r₁, hr₁pos, hr₁ball⟩ := Metric.isOpen_iff.mp hU a haU
  rcases Finset.eq_empty_or_nonempty (T.erase a) with hS | hS
  · exact ⟨r₁, hr₁pos, hr₁ball, fun b hbT hba => by
      have : b ∈ T.erase a := Finset.mem_erase.mpr ⟨hba, hbT⟩
      simp [hS] at this⟩
  · have hpos : ∀ b ∈ T.erase a, 0 < dist a b := fun b hb =>
      dist_pos.mpr (Ne.symm (Finset.mem_erase.mp hb).1)
    set r₂ := (T.erase a).inf' hS (dist a)
    have hr₂pos : 0 < r₂ := by
      rw [Finset.lt_inf'_iff]; exact hpos
    refine ⟨min r₁ (r₂ / 2), lt_min hr₁pos (half_pos hr₂pos),
      (Metric.ball_subset_ball (min_le_left _ _)).trans hr₁ball, ?_⟩
    intro b hbT hba hball
    have hbS : b ∈ T.erase a := Finset.mem_erase.mpr ⟨hba, hbT⟩
    have hle : r₂ ≤ dist a b := Finset.inf'_le _ hbS
    rw [Metric.mem_ball, dist_comm] at hball
    linarith [min_le_right r₁ (r₂ / 2)]

end Problems.residue_thm
