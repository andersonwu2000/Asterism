import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_three_lte_upper_lifting

namespace Problems.Minif2f.imo_1990_p3

-- Decompose n = 3^k · m with k = v₃(n), m = n / 3^k. Then m is odd and 3 ∤ m.
-- Reduces the factorization upper bound v₃(2^n+1) ≤ 1 + v₃(n) to the prime-3 LTE
-- upper bound `three_lte_upper_lifting`: ¬ 3^(k+2) ∣ 2^(3^k·m)+1 for m odd, 3∤m.
theorem s9764 :
    ∀ (n : ℕ), 2 ≤ n → Odd n → 3 ∣ n →
      (2 ^ n + 1).factorization 3 ≤ 1 + n.factorization 3 := by
  intro n hn hodd h3
  have h_ord_dvd : 3 ^ n.factorization 3 ∣ n := Nat.ordProj_dvd n 3
  have h_n_eq : n = 3 ^ n.factorization 3 * (n / 3 ^ n.factorization 3) :=
    (Nat.mul_div_cancel' h_ord_dvd).symm
  have h_not_dvd : ¬ 3 ∣ (n / 3 ^ n.factorization 3) :=
    Nat.not_dvd_ordCompl Nat.prime_three (by omega)
  have h_odd_m : Odd (n / 3 ^ n.factorization 3) :=
    Odd.of_dvd_nat hodd (Nat.div_dvd_of_dvd h_ord_dvd)
  have h_lifting := three_lte_upper_lifting
  have h_upper : ¬ 3 ^ (n.factorization 3 + 2) ∣ 2 ^ n + 1 := by
    have key := h_lifting (n.factorization 3) (n / 3 ^ n.factorization 3) h_odd_m h_not_dvd
    rw [← h_n_eq] at key
    exact key
  by_contra h
  push Not at h
  apply h_upper
  have hne : 2 ^ n + 1 ≠ 0 := by positivity
  rw [Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three hne]
  omega
end Problems.Minif2f.imo_1990_p3
