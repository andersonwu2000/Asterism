import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_pow_27_dvd_n
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_pow_32_dvd_n

namespace Problems.Minif2f.mathd_numbertheory_709

-- Split `864 ∣ n` into prime-power factors: `32 ∣ n` and `27 ∣ n`.
-- Since `Nat.Coprime 32 27` (gcd = 1), their product `32 * 27 = 864` also divides n.
-- Each sub-goal isolates a single prime tower, strictly simpler than the joint divisibility.
theorem s9621 : ∀ (n : ℕ) (h₀ : 0 < n) (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
    (h₂ : Finset.card (Nat.divisors (3 * n)) = 30), (864 : ℕ) ∣ n  := by
  intro n h₀ h₁ h₂
  have h32 : (32 : ℕ) ∣ n := pow_32_dvd_n n h₀ h₁ h₂
  have h27 : (27 : ℕ) ∣ n := pow_27_dvd_n n h₀ h₁ h₂
  have hcop : Nat.Coprime 32 27 := by decide
  exact hcop.mul_dvd_of_dvd_of_dvd h32 h27

end Problems.Minif2f.mathd_numbertheory_709
