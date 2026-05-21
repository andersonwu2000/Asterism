import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integral_radius_independence
import Problems.residue_thm.proofs.L_residue_dif_pos_unfold

namespace Problems.residue_thm

-- Decompose into: (1) radius-independence of the circle integral on a punctured
-- analytic ball, and (2) unfolding `Complex.residue` via `dif_pos` + `Classical.choose`.
-- Bridge via a shared small radius ρ < min(R, R'), where R' = Classical.choose for residue.
theorem s10275 {f : ℂ → ℂ} {z₀ : ℂ} {R r : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (hr : 0 < r) (hrR : r < R) :
    (1 / (2 * Real.pi * Complex.I)) * ∮ z in C(z₀, r), f z =
      Complex.residue f z₀  := by
  have hR : 0 < R := hr.trans hrR
  have h_exists : ∃ R' : ℝ, 0 < R' ∧ AnalyticOn ℂ f (Metric.ball z₀ R' \ {z₀}) :=
    ⟨R, hR, hf⟩
  set R' := Classical.choose h_exists with hR'_def
  have hR'_pos : 0 < R' := (Classical.choose_spec h_exists).1
  have hf' : AnalyticOn ℂ f (Metric.ball z₀ R' \ {z₀}) :=
    (Classical.choose_spec h_exists).2
  set ρ := min R R' / 2 with hρ_def
  have hmin_pos : 0 < min R R' := lt_min hR hR'_pos
  have hρ_pos : 0 < ρ := by show 0 < min R R' / 2; linarith

  have hρ_lt_R : ρ < R := by
    have h1 : min R R' ≤ R := min_le_left _ _
    have : ρ ≤ R / 2 := by
      simp [hρ_def]
      exact div_le_div_of_nonneg_right h1 (by norm_num)
    linarith
  have hρ_lt_R' : ρ < R' := by
    have h1 : min R R' ≤ R' := min_le_right _ _
    have : ρ ≤ R' / 2 := by
      simp [hρ_def]
      exact div_le_div_of_nonneg_right h1 (by norm_num)
    linarith
  have h_R'2_lt_R' : R' / 2 < R' := by linarith
  have h_R'2_pos : 0 < R' / 2 := by linarith
  have eq1 : (∮ z in C(z₀, r), f z) = (∮ z in C(z₀, ρ), f z) :=
    circle_integral_radius_independence hf hr hrR hρ_pos hρ_lt_R
  have eq2 : (∮ z in C(z₀, ρ), f z) = (∮ z in C(z₀, R'/2), f z) :=
    circle_integral_radius_independence hf' hρ_pos hρ_lt_R' h_R'2_pos h_R'2_lt_R'
  rw [eq1, eq2]
  exact (residue_dif_pos_unfold h_exists).symm

end Problems.residue_thm
