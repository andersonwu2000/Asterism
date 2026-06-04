import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_factorization_eq_two_pow_three_pow

namespace Problems.Minif2f.mathd_numbertheory_709

-- Choose explicit witnesses a := n.factorization 2, b := n.factorization 3;
-- existence then reduces to the concrete factorization equation.
theorem s9739 :
    ∀ (n : ℕ) (_h₀ : 0 < n)
      (_h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (_h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      (∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3) → ∃ a b, n = 2 ^ a * 3 ^ b  := by
  intro n h₀ h₁ h₂ hsmooth
  have hfact := factorization_eq_two_pow_three_pow n h₀ h₁ h₂ hsmooth
  exact ⟨n.factorization 2, n.factorization 3, hfact⟩

end Problems.Minif2f.mathd_numbertheory_709
