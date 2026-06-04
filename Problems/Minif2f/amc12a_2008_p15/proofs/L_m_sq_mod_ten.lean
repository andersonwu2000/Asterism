import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs

namespace Problems.Minif2f.amc12a_2008_p15

-- m_sq_mod_ten: Nat.pow_mod reduces m^2 % 10 to (m % 10)^2 % 10;
-- substituting m % 10 = 0 gives 0^2 % 10 = 0, closed by rfl.
theorem m_sq_mod_ten : ∀ (m : ℕ),
    m % 10 = 0 → m % 4 = 0 → 4 ≤ m → m^2 % 10 = 0 := by
  intro m hm10 _hm4 _hm_ge
  rw [Nat.pow_mod]
  rw [hm10]

end Problems.Minif2f.amc12a_2008_p15
