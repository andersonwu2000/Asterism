import Mathlib
import Problems.Minif2f.mathd_numbertheory_33.Defs

namespace Problems.Minif2f.mathd_numbertheory_33

-- Bounded brute force: `interval_cases n` (using h₀ : n < 398) splits into the
-- 398 finite candidates for n; `omega` discharges each using h₁ : n * 7 % 398 = 1
-- (only n = 57 satisfies 57 * 7 = 399 = 398 + 1, the rest contradict h₁).
-- Leaf-level: no sub-goals — modular arithmetic on a small finite range.
theorem s721 : ∀ (n : ℕ) (h₀ : n < 398) (h₁ : n * 7 % 398 = 1), n = 57  := by
  intro n h₀ h₁
  interval_cases n <;> omega

end Problems.Minif2f.mathd_numbertheory_33
