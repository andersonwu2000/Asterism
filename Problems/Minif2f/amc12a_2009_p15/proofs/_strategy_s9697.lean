import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_re_98_plus_4j_eq

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce m ≥ 98 with m % 4 = 2 to j-parametric form m = 98 + 4j; the sole
-- sub-goal is a closed form Re(S(98+4j)) = -50 - 2j (induction on j: base
-- m=98 evaluates to -50; each +4 step decreases Re by 2 since I^(m+1..m+4)
-- contributes -2 to the real part when m % 4 = 2). The parent bound then
-- follows by dropping the non-negative -2j summand.
theorem s9697 : ∀ (m : ℕ), 97 < m → m % 4 = 2 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).re ≤ -50  := by
  intro m hm hmod
  have h_aux := sum_re_98_plus_4j_eq ((m - 98) / 4)
  have heq : m = 98 + 4 * ((m - 98) / 4) := by omega
  rw [heq, h_aux]
  have hjpos : (0 : ℝ) ≤ ((m - 98) / 4 : ℕ) := by positivity
  linarith
end Problems.Minif2f.amc12a_2009_p15
