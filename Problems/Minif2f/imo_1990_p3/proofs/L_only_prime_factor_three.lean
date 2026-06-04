import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- only_prime_factor_three: every prime dividing m is 3
-- Odd m rules out p=2 (omega); hno5 rules out p≥5; interval_cases [2,5) closes p=4 via decide.
theorem only_prime_factor_three :
    ∀ (m : ℕ), 2 ≤ m → Odd m → 3 ∣ m → ¬ (9 ∣ m) →
      (∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ m) →
      ∀ p, Nat.Prime p → p ∣ m → p = 3 := by
  intro m _hm hodd _h3 _h9 hno5 p hp hpdvd
  have hp2 : p ≠ 2 := by
    intro heq; subst heq
    obtain ⟨k, hk⟩ := hpdvd
    obtain ⟨j, hj⟩ := hodd
    omega
  have hp5 : p < 5 := by
    by_contra h
    push Not at h
    exact absurd hpdvd (hno5 p hp h)
  have h2le : 2 ≤ p := hp.two_le
  interval_cases p <;> simp_all (config := { decide := true })

end Problems.Minif2f.imo_1990_p3
