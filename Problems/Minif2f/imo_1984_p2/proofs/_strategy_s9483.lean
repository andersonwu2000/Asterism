import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs
import Problems.Minif2f.imo_1984_p2.proofs.L_cancel_coprime_factors
import Problems.Minif2f.imo_1984_p2.proofs.L_seven_pow_dvd_of_pow_dvd_sq

namespace Problems.Minif2f.imo_1984_p2

-- Two-step prime cancellation: first peel the single factor of 7 plus the three
-- coprime-to-7 factors (x, y, x+y) to land at 7^6 ∣ Q^2; then use the prime-square
-- valuation lemma to halve the exponent, yielding 7^3 ∣ Q where Q = x^2+x*y+y^2.
theorem s9483 : ∀ (x y : ℤ), ¬7 ∣ x → ¬7 ∣ y → ¬7 ∣ x + y →
    (7:ℤ) ^ 7 ∣ 7 * x * y * (x + y) * (x ^ 2 + x * y + y ^ 2) ^ 2 →
    (7:ℤ) ^ 3 ∣ x ^ 2 + x * y + y ^ 2  := by
  intro x y hx hy hxy hdvd
  have h1 : (7:ℤ) ^ 6 ∣ (x ^ 2 + x * y + y ^ 2) ^ 2 :=
    cancel_coprime_factors x y hx hy hxy hdvd
  exact seven_pow_dvd_of_pow_dvd_sq _ h1

end Problems.Minif2f.imo_1984_p2
