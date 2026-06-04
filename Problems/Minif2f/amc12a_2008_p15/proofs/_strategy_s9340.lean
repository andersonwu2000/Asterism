import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs.L_m_sq_mod_ten
import Problems.Minif2f.amc12a_2008_p15.proofs.L_two_pow_mod_ten

namespace Problems.Minif2f.amc12a_2008_p15

-- Decompose `(m^2 + 2^m) % 10 = 6` (for m % 10 = 0, m % 4 = 0, 4 ≤ m) into:
-- (1) m^2 % 10 = 0 (from m % 10 = 0), (2) 2^m % 10 = 6 (from m % 4 = 0 ∧ 4 ≤ m).
-- omega closes (m^2 + 2^m) % 10 = 6 from the two mod facts via linear arithmetic on ℕ.
theorem s9340 : ∀ (m : ℕ),
    m % 10 = 0 → m % 4 = 0 → 4 ≤ m → (m^2 + 2^m) % 10 = 6  := by
  intro m hm10 hm4 hm_ge
  have h_sq : m^2 % 10 = 0 := m_sq_mod_ten m hm10 hm4 hm_ge
  have h_pow : 2^m % 10 = 6 := two_pow_mod_ten m hm10 hm4 hm_ge
  omega

end Problems.Minif2f.amc12a_2008_p15
