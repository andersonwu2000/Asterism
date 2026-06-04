import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_only_prime_factor_three

namespace Problems.Minif2f.imo_1990_p3

-- Every prime factor of `m` is forced to be 3: Odd ⇒ no 2; hypothesis ⇒ no p≥5;
-- so the only prime in [3,5) divides m, hence m = 3 ^ v₃(m) by `prod_factorization_pow_eq_self`.
theorem s9730 :
    ∀ (m : ℕ), 2 ≤ m → Odd m → 3 ∣ m → ¬ (9 ∣ m) →
      (∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ m) →
      m = 3 ^ m.factorization 3  := by
  intro m hm hodd h3 h9 hno
  have h_only : ∀ p, Nat.Prime p → p ∣ m → p = 3 :=
    only_prime_factor_three m hm hodd h3 h9 hno
  have hm0 : m ≠ 0 := by omega
  have hfact : m.factorization = Finsupp.single 3 (m.factorization 3) := by
    ext p
    by_cases hp_eq : p = 3
    · subst hp_eq; simp
    · simp [Finsupp.single_apply, hp_eq]
      by_cases hp_prime : p.Prime
      · have hpnd : ¬ p ∣ m := fun hpdvd => hp_eq (h_only p hp_prime hpdvd)
        exact Nat.factorization_eq_zero_of_not_dvd hpnd
      · exact Nat.factorization_eq_zero_of_not_prime m hp_prime
  have hself := Nat.prod_factorization_pow_eq_self hm0
  rw [hfact] at hself
  rw [Finsupp.prod_single_index (by simp)] at hself
  exact hself.symm

end Problems.Minif2f.imo_1990_p3
