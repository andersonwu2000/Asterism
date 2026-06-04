import Mathlib
import Problems.Minif2f.mathd_algebra_123.Defs

namespace Problems.Minif2f.mathd_algebra_123

-- Direct closure: linear arithmetic over ℕ.
-- From a + b = 20 and a = 3 * b, substitution gives 4 * b = 20, so b = 5, a = 15, hence a - b = 10.
-- `omega` discharges this linear system over ℕ in one step; no sub-goals needed.
theorem s633 : ∀ (a b : ℕ) (h₀ : 0 < a ∧ 0 < b) (h₁ : a + b = 20) (h₂ : a = 3 * b), a - b = 10  := by
  intro a b h₀ h₁ h₂
  omega


end Problems.Minif2f.mathd_algebra_123
