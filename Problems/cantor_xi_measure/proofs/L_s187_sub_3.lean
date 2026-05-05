import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set MeasureTheory

/-- The Haar measure of the homothety image: `volume (homothety 1 r '' S) = ofReal r · volume S`
    when `r = (1-ξ)/2 > 0`. Uses `addHaar_image_homothety` + `finrank ℝ ℝ = 1` + `abs_of_pos`. -/
theorem s187_sub_3 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ∀ n : ℕ,
    MeasureTheory.volume (AffineMap.homothety (1 : ℝ) ((1 - ξ) / 2) '' cantorXi ξ n) =
    ENNReal.ofReal ((1 - ξ) / 2) * MeasureTheory.volume (cantorXi ξ n) := by
  intro ξ hξ_pos hξ_lt n
  rw [MeasureTheory.Measure.addHaar_image_homothety]
  have hpos : (0 : ℝ) < (1 - ξ) / 2 := by linarith
  simp only [Module.finrank_self, pow_one, abs_of_pos hpos]

end Problems.cantor_xi_measure
