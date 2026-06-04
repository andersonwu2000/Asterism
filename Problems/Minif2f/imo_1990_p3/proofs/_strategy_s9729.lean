import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_factorization_three_upper_le

namespace Problems.Minif2f.imo_1990_p3

-- Reformulate the negative-divisibility goal as a factorization upper bound.
-- `factorization_three_upper_le` claims v₃(2^n+1) ≤ 1 + v₃(n); pair with
-- `Nat.Prime.pow_dvd_iff_le_factorization` (and the fact that 2^n+1 ≠ 0) to
-- transport into the ¬-divisibility form. The factorization-inequality shape
-- exposes Nat-valued arithmetic suitable for `omega` and recursive bounds on
-- v₃ — cleaner to attack than the contrapositive directly.
theorem s9729 :
    ∀ (n : ℕ), 2 ≤ n → Odd n → 3 ∣ n →
      ¬ 3 ^ (2 + n.factorization 3) ∣ (2 ^ n + 1)  := by
  intro n hn hodd h3
  have h_le := factorization_three_upper_le n hn hodd h3
  intro h_dvd
  have h2n_ne : (2 ^ n + 1) ≠ 0 := by positivity
  have h_ge : 2 + n.factorization 3 ≤ (2 ^ n + 1).factorization 3 :=
    (Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three h2n_ne).mp h_dvd
  omega
end Problems.Minif2f.imo_1990_p3
