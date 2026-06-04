import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_709

-- factorize_when_two_three_smooth_2: if all prime factors of n are 2 or 3, write n = 2^a * 3^b
-- via factorization finsupp: support ⊆ {2,3} + prod_factorization_pow_eq_self + prod over {2,3}
theorem factorize_when_two_three_smooth_2 :
    ∀ (n : ℕ) (h₀ : 0 < n)
      (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      (∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3) → ∃ a b, n = 2 ^ a * 3 ^ b := by
  intro n h₀ _h₁ _h₂ hsmooth
  refine ⟨n.factorization 2, n.factorization 3, ?_⟩
  have hn : n ≠ 0 := h₀.ne'
  have hsupp : n.factorization.support ⊆ {2, 3} := by
    intro p hp
    rw [Nat.support_factorization] at hp
    rw [Finset.mem_insert, Finset.mem_singleton]
    exact hsmooth p (Nat.mem_primeFactors.mp hp).1 (Nat.mem_primeFactors.mp hp).2.1
  calc n = n.factorization.prod (· ^ ·) := (Nat.prod_factorization_pow_eq_self hn).symm
    _ = ∏ p ∈ ({2, 3} : Finset ℕ), p ^ n.factorization p := by
        apply Finsupp.prod_of_support_subset _ hsupp
        simp
    _ = 2 ^ n.factorization 2 * 3 ^ n.factorization 3 := by simp [Finset.prod_insert]

end Problems.Minif2f.mathd_numbertheory_709
