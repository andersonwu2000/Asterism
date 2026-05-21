import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- residue_dif_pos_unfold: unfold Complex.residue via dif_pos to expose the Classical.choose integral
-- entry_kind: Builder
theorem residue_dif_pos_unfold {f : ℂ → ℂ} {z₀ : ℂ}
    (h : ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    Complex.residue f z₀ =
      (1 / (2 * Real.pi * Complex.I)) *
        ∮ z in C(z₀, Classical.choose h / 2), f z := by
  simp only [Complex.residue, dif_pos h]

end Problems.residue_thm
