import Mathlib
import Problems.Minif2f.amc12_2000_p5.Defs

namespace Problems.Minif2f.amc12_2000_p5

-- Direct: x < 2 ⇒ x - 2 < 0 ⇒ |x - 2| = 2 - x = p; conclude x - p = 2 - 2p by linarith.
theorem s564 : ∀ (x p : ℝ) (h₀ : x < 2) (h₁ : abs (x - 2) = p), x - p = 2 - 2 * p  := by
  intro x p h₀ h₁
  have hp : p = 2 - x := by
    rw [← h₁, abs_of_neg (by linarith : x - 2 < 0)]
    ring
  linarith

end Problems.Minif2f.amc12_2000_p5
