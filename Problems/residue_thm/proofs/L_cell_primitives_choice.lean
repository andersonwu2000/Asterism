import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- cell_primitives_choice: Classical.choose of isExactOn_ball per cell gives P i j
theorem cell_primitives_choice
    {U : Set ℂ} {g : ℂ → ℂ}
    (hg : AnalyticOn ℂ g U)
    (N : ℕ) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hball : ∀ i j, i < N → j < N → Metric.ball (c i j) (r i j) ⊆ U) :
    ∃ P : ℕ → ℕ → ℂ → ℂ,
      ∀ i j, i < N → j < N →
        ∀ z ∈ Metric.ball (c i j) (r i j), HasDerivAt (P i j) (g z) z := by
  refine ⟨fun i j =>
    if hi : i < N then
      if hj : j < N then
        Classical.choose ((hg.mono (hball i j hi hj)).differentiableOn.isExactOn_ball)
      else fun _ => 0
    else fun _ => 0, ?_⟩
  intro i j hi hj z hz
  simp only [hi, hj, dif_pos]
  exact Classical.choose_spec
    ((hg.mono (hball i j hi hj)).differentiableOn.isExactOn_ball) z hz

end Problems.residue_thm
