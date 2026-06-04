import Mathlib
import Problems.Minif2f.mathd_algebra_234.Defs

namespace Problems.Minif2f.mathd_algebra_234

-- Direct: solve h₀ for d = 5/3 by linarith, then cube and reduce by ring.
theorem s653 : ∀ (d : ℝ) (h₀ : 27 / 125 * d = 9 / 25), 3 / 5 * d ^ 3 = 25 / 9  := by
  intro d h₀
  have hd : d = 5 / 3 := by linarith
  rw [hd]; ring

end Problems.Minif2f.mathd_algebra_234
