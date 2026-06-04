import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs
import Problems.Minif2f.mathd_numbertheory_43.proofs.L_five_factorization_factorial_942_ge_233

namespace Problems.Minif2f.mathd_numbertheory_43

-- Reduce p^k ∣ n! to k ≤ (n!).factorization p via Nat.Prime.pow_dvd_iff_le_factorization.
-- Sub-goal: 233 ≤ (942!).factorization 5 — a single-prime Legendre-formula bound,
-- strictly simpler than the divisibility statement and abstract from p=5 specifics.
theorem s9625 : (5 : ℕ) ^ 233 ∣ Nat.factorial 942  := by
  have hp : Nat.Prime 5 := by decide
  have hfact := five_factorization_factorial_942_ge_233
  exact (hp.pow_dvd_iff_le_factorization (Nat.factorial_ne_zero 942)).mpr hfact

end Problems.Minif2f.mathd_numbertheory_43
