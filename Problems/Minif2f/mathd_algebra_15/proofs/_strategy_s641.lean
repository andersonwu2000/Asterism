import Mathlib
import Problems.Minif2f.mathd_algebra_15.Defs

namespace Problems.Minif2f.mathd_algebra_15

-- Direct: instantiate h₀ at (2,6) with positivity, then evaluate 2^6 + 6^2 = 100.

theorem s641 : ∀ (s : ℕ → ℕ → ℕ) (h₀ : ∀ a b, 0 < a ∧ 0 < b → s a b = a ^ (b : ℕ) + b ^ (a : ℕ)), s 2 6 = 100  := by
  intro s h₀
  rw [h₀ 2 6 ⟨by norm_num, by norm_num⟩]
  norm_num

end Problems.Minif2f.mathd_algebra_15
