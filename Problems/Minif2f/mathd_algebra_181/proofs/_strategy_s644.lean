import Mathlib
import Problems.Minif2f.mathd_algebra_181.Defs

namespace Problems.Minif2f.mathd_algebra_181

-- Direct proof: clear the division by `n - 3 ≠ 0` via `field_simp`, then close
-- the resulting linear equation `n + 5 = 2 * (n - 3)` with `linarith`.
theorem s644 : ∀ (n : ℝ) (h₀ : n ≠ 3) (h₁ : (n + 5) / (n - 3) = 2), n = 11  := by
  intro n h₀ h₁
  have h2 : n - 3 ≠ 0 := sub_ne_zero.mpr h₀
  field_simp at h₁
  linarith

end Problems.Minif2f.mathd_algebra_181
