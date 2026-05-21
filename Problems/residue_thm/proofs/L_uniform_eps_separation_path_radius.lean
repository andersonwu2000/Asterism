import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- uniform_eps_separation_path_radius: compactness of γ([0,1]) gives uniform separation from a;
-- min with R/2 keeps ε < R.
theorem uniform_eps_separation_path_radius
    {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∃ ε : ℝ, 0 < ε ∧ ε < R ∧ ∀ t ∈ Set.Icc (0 : ℝ) 1, ε < dist (γ t) a := by
  have hcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have hpos : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 < dist (γ t) a :=
    fun t ht => dist_pos.mpr (h_avoid t ht)
  have hcont_dist : ContinuousOn (fun t => dist (γ t) a) (Set.Icc 0 1) :=
    fun t ht => (hcont t ht).dist continuousWithinAt_const
  have hne : (Set.Icc (0 : ℝ) 1).Nonempty := Set.nonempty_Icc.mpr zero_le_one
  obtain ⟨t₀, ht₀, hmin⟩ := isCompact_Icc.exists_isMinOn hne hcont_dist
  have hε_pos : 0 < dist (γ t₀) a := hpos t₀ ht₀
  refine ⟨min (dist (γ t₀) a / 2) (R / 2), lt_min (by linarith) (by linarith),
         min_lt_of_right_lt (by linarith), fun t ht => ?_⟩
  exact lt_of_le_of_lt (min_le_left _ _) (lt_of_lt_of_le (by linarith) (hmin ht))

end Problems.residue_thm
