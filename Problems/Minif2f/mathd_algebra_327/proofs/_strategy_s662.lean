import Mathlib
import Problems.Minif2f.mathd_algebra_327.Defs

namespace Problems.Minif2f.mathd_algebra_327

-- direct: clear h₀ to |9 + 2a| < 5, expand abs_lt, two linarith for the conjunction.
theorem s662 : ∀ (a : ℝ) (h₀ : 1 / 5 * abs (9 + 2 * a) < 1), -7 < a ∧ a < -2  := by
  intro a h₀
  have h1 : abs (9 + 2 * a) < 5 := by linarith
  rw [abs_lt] at h1
  exact ⟨by linarith, by linarith⟩

end Problems.Minif2f.mathd_algebra_327
