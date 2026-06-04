import Mathlib
import Problems.Minif2f.mathd_numbertheory_136.Defs

namespace Problems.Minif2f.mathd_numbertheory_136

-- Linear Diophantine equation over ℕ; unique solution n=321 (123*321+17=39500).
-- Direct closure by `omega` — no decomposition needed.
theorem s697 : ∀ (n : ℕ) (h₀ : 123 * n + 17 = 39500), n = 321  := by
  intro n h₀
  omega

end Problems.Minif2f.mathd_numbertheory_136
