import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_smooth_at_6
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_smooth_forces_864

namespace Problems.Minif2f.mathd_numbertheory_709

-- Split along prime support, not via Nat.dvd_antisymm (dead in s9439).
-- A. `smooth_at_6`: every prime dividing n is 2 or 3 (τ(2n)=28 ∧ τ(3n)=30 ⇒
--    the coprime-to-6 part has τ=1 by gcd(28,30)=2 analysis ruling out τ=2).
-- B. `smooth_forces_864`: with n's prime support ⊆ {2,3}, write n = 2^a·3^b
--    and solve (a+2)(b+1)=28, (a+1)(b+2)=30 ⇒ a=5, b=3 ⇒ n = 864.
theorem s9657 : ∀ (n : ℕ) (h₀ : 0 < n) (h₁ : Finset.card (Nat.divisors (2 * n)) = 28) (h₂ : Finset.card (Nat.divisors (3 * n)) = 30), n = 864  := by
  intro n h₀ h₁ h₂
  have h_smooth : ∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3 :=
    smooth_at_6 n h₀ h₁ h₂
  exact smooth_forces_864 n h₀ h₁ h₂ h_smooth

end Problems.Minif2f.mathd_numbertheory_709
