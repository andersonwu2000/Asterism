import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_exists_two_three_factorization
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_factorization_forces_864

namespace Problems.Minif2f.mathd_numbertheory_709

-- Split: extract 2^a·3^b factorization from {2,3} prime support, then solve τ-equations.
-- A. `exists_two_three_factorization` reduces the prime-support hypothesis to existence
--    of (a, b) with n = 2^a · 3^b — pure number-theory existence, no algebra.
-- B. `factorization_forces_864` does the algebra in (a, b): from τ(2·2^a·3^b)=(a+2)(b+1)=28
--    and τ(3·2^a·3^b)=(a+1)(b+2)=30 conclude a=5, b=3, so n = 2^5·3^3 = 864.
theorem s9700 : ∀ (n : ℕ) (h₀ : 0 < n) (h₁ : Finset.card (Nat.divisors (2 * n)) = 28) (h₂ : Finset.card (Nat.divisors (3 * n)) = 30), (∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3) → n = 864  := by
  intro n h₀ h₁ h₂ hsupp
  obtain ⟨a, b, hn⟩ := exists_two_three_factorization n h₀ h₁ h₂ hsupp
  exact factorization_forces_864 n h₀ h₁ h₂ hsupp a b hn

end Problems.Minif2f.mathd_numbertheory_709
