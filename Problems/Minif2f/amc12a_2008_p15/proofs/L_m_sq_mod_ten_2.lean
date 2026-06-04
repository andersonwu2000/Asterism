import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs

namespace Problems.Minif2f.amc12a_2008_p15

-- m_sq_mod_ten_2: m % 10 = 0 → m^2 % 10 = 0 via Nat.pow_mod + substitution
theorem m_sq_mod_ten_2 : ∀ (m : ℕ),
    m % 10 = 0 → m % 4 = 0 → 4 ≤ m → m ^ 2 % 10 = 0 := by
  intro m hm _ _
  rw [Nat.pow_mod, hm]

end Problems.Minif2f.amc12a_2008_p15
