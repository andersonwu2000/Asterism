import Mathlib
import Problems.Minif2f.mathd_numbertheory_780.Defs
import Problems.Minif2f.mathd_numbertheory_780.proofs.L_dvd_215_in_range_eq_43
import Problems.Minif2f.mathd_numbertheory_780.proofs.L_m_dvd_215

namespace Problems.Minif2f.mathd_numbertheory_780

-- Decompose into: (a) m divides 215, derived from the two modular hypotheses,
-- (b) any divisor of 215 lying in [10, 99] equals 43.
-- Combine: apply (a) to obtain m ∣ 215, then (b) with the range constraint.
theorem s745 : ∀ (m x : ℤ) (h₀ : 0 ≤ x) (h₁ : 10 ≤ m ∧ m ≤ 99) (h₂ : 6 * x % m = 1) (h₃ : (x - 6 ^ 2) % m = 0), m = 43  := by
  intro m x h₀ h₁ h₂ h₃
  have h_dvd : m ∣ 215 := m_dvd_215 m x h₀ h₁ h₂ h₃
  exact dvd_215_in_range_eq_43 m h₁ h_dvd

end Problems.Minif2f.mathd_numbertheory_780
