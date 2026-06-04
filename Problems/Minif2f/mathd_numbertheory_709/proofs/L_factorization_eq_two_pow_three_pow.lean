import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- factorization_eq_two_pow_three_pow: if all prime factors of n are 2 or 3, then
-- n equals 2^(v₂ n) * 3^(v₃ n) by restricting the factorization support to {2, 3}.
theorem factorization_eq_two_pow_three_pow :
    ∀ (n : ℕ) (_h₀ : 0 < n)
      (_h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (_h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      (∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3) →
      n = 2 ^ (n.factorization 2) * 3 ^ (n.factorization 3) := by
  intro n h₀ _h₁ _h₂ hp
  have hn : n ≠ 0 := Nat.pos_iff_ne_zero.mp h₀
  have hsup : n.factorization.support ⊆ {2, 3} := by
    intro p hp_mem
    rw [Nat.support_factorization] at hp_mem
    have hprime : p.Prime := Nat.prime_of_mem_primeFactors hp_mem
    have hdvd : p ∣ n := Nat.dvd_of_mem_primeFactors hp_mem
    rcases hp p hprime hdvd with h | h <;> simp [h]
  calc n
      = n.factorization.prod (· ^ ·) := (Nat.prod_factorization_pow_eq_self hn).symm
    _ = ∏ a ∈ n.factorization.support, a ^ (n.factorization a) := rfl
    _ = ∏ a ∈ ({2, 3} : Finset ℕ), a ^ (n.factorization a) :=
        Finset.prod_subset hsup (fun x _ hx => by
          have h0 : n.factorization x = 0 := Finsupp.notMem_support_iff.mp hx
          simp [h0])
    _ = 2 ^ n.factorization 2 * 3 ^ n.factorization 3 := by
        simp [Finset.prod_insert (show (2:ℕ) ∉ ({3} : Finset ℕ) from by decide),
              Finset.prod_singleton]

end Problems.Minif2f.mathd_numbertheory_709
