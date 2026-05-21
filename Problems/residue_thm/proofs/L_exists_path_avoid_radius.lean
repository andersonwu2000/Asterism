import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- exists_path_avoid_radius: compactness of γ(Icc 0 1) gives positive minimum distance to a
theorem exists_path_avoid_radius
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_repr : ∀ z : ℂ, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), P w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    ∃ ε : ℝ, 0 < ε ∧ ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a := by
  have hcont : ContinuousOn (fun t => dist (γ t) a) (Set.Icc 0 1) := by
    simp_rw [dist_eq_norm]
    exact (hγ.continuousOn.sub continuousOn_const).norm
  have hpos : ∀ t ∈ Set.Icc (0:ℝ) 1, 0 < dist (γ t) a :=
    fun t ht => dist_pos.mpr (h_avoid t ht)
  obtain ⟨t₀, ht₀, hmin⟩ := isCompact_Icc.exists_isMinOn
    (Set.nonempty_Icc.mpr zero_le_one) hcont
  exact ⟨dist (γ t₀) a / 2, half_pos (hpos t₀ ht₀),
    fun t ht => lt_of_lt_of_le (half_lt_self (hpos t₀ ht₀)) (hmin ht)⟩


end Problems.residue_thm

