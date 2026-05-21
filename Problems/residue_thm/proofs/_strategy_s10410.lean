import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_annulus_residue_diff

namespace Problems.residue_thm

-- Strip the g, P, hg_eq, hP_eq layer by choosing concrete radii
-- `r := (dist z z₀ + R)/2` (so `dist z z₀ < r < R`) and `ε := dist z z₀ / 2`
-- (so `0 < ε < dist z z₀ < R`). The single sub-goal `annulus_residue_diff`
-- supplies the annular residue identity `(∮ outer f(w)/(w-z)) - (∮ inner f(w)/(w-z))
-- = 2πi · f(z)`; combining with `hg_eq`, `hP_eq` reduces `f z = g z + P z`
-- to a `field_simp`/`ring` arithmetic step.
theorem s10410
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (g P : ℂ → ℂ)
    (hg_eq : ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
      g z = (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, r), f w / (w - z))
    (hP_eq : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
      P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, ε), f w / (w - z))) :
    ∀ z ∈ Metric.ball z₀ R \ {z₀}, f z = g z + P z  := by
  intro z hz
  obtain ⟨hzB, hzS⟩ := hz
  have hzNe : z ≠ z₀ := fun h => hzS (by simp [h])
  have hd_pos : 0 < dist z z₀ := dist_pos.mpr hzNe
  have hd_lt_R : dist z z₀ < R := Metric.mem_ball.mp hzB
  set r : ℝ := (dist z z₀ + R) / 2 with hr_def
  set ε : ℝ := dist z z₀ / 2 with hε_def
  have hr_lb : dist z z₀ < r := by
    change dist z z₀ < (dist z z₀ + R) / 2; linarith
  have hr_ub : r < R := by
    change (dist z z₀ + R) / 2 < R; linarith
  have hε_pos : 0 < ε := by
    change 0 < dist z z₀ / 2; linarith
  have hε_lt_d : ε < dist z z₀ := by
    change dist z z₀ / 2 < dist z z₀; linarith
  have hε_lt_R : ε < R := lt_trans hε_lt_d hd_lt_R
  have h_main :=
    annulus_residue_diff hR hf hzB hzNe hr_lb hr_ub hε_pos hε_lt_d
  have hg_val := hg_eq z hzB r hr_lb hr_ub
  have hP_val := hP_eq z hzNe ε hε_pos hε_lt_d hε_lt_R
  have h2pi : (2 * (Real.pi : ℂ) * Complex.I) ≠ 0 := by
    have hπ : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    simp [hπ, Complex.I_ne_zero]
  rw [hg_val, hP_val]
  field_simp
  linear_combination -h_main

end Problems.residue_thm
