import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set MeasureTheory

/-- ENNReal arithmetic: two copies of `ofReal((1-ξ)/2)·ofReal((1-ξ)^n)` sum to `ofReal((1-ξ)^(n+1))`. -/
theorem s185_sub_5 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ,
    ENNReal.ofReal ((1 - ξ) / 2) * ENNReal.ofReal ((1 - ξ) ^ n) +
    ENNReal.ofReal ((1 - ξ) / 2) * ENNReal.ofReal ((1 - ξ) ^ n) =
    ENNReal.ofReal ((1 - ξ) ^ (n + 1)) := by
  intro ξ hξ_pos hξ_lt n
  have h0 : (0 : ℝ) ≤ 1 - ξ := by linarith
  have h1 : (0 : ℝ) ≤ (1 - ξ) / 2 := by linarith
  have h2 : (0 : ℝ) ≤ (1 - ξ) ^ n := pow_nonneg h0 n
  have h3 : (0 : ℝ) ≤ (1 - ξ) / 2 * (1 - ξ) ^ n := mul_nonneg h1 h2
  rw [← ENNReal.ofReal_mul h1, ← ENNReal.ofReal_add h3 h3]
  congr 1
  rw [pow_succ]
  ring

end Problems.cantor_xi_measure
