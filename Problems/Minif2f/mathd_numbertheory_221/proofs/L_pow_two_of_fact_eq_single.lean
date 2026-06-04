import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_221

-- pow_two_of_fact_eq_single: reconstruct x = p^2 from factorization = Finsupp.single p 2
-- Uses Nat.prod_factorization_pow_eq_self + Finsupp.prod_single_index.
theorem pow_two_of_fact_eq_single :
    ∀ x p : ℕ, p.Prime → x.factorization = Finsupp.single p 2 → x = p^2 := by
  intro x p hp hfact
  have hx0 : x ≠ 0 := by
    intro h
    simp [h, Nat.factorization_zero] at hfact
    exact (Finsupp.single_ne_zero.mpr (by norm_num)) hfact.symm
  have key := Nat.prod_factorization_pow_eq_self hx0
  rw [hfact, Finsupp.prod_single_index (by simp)] at key
  exact key.symm

end Problems.Minif2f.mathd_numbertheory_221
