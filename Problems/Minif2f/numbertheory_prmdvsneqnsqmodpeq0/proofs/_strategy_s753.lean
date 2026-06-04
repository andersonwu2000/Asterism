import Mathlib
import Problems.Minif2f.numbertheory_prmdvsneqnsqmodpeq0.Defs

namespace Problems.Minif2f.numbertheory_prmdvsneqnsqmodpeq0

-- Direct proof: rewrite `n^2 % p = 0` as `↑p ∣ n^2`, then split the iff.
-- Forward uses `dvd_pow`; backward uses primality via `Prime.dvd_of_dvd_pow`.
theorem s753 : ∀ (n : ℤ) (p : ℕ) (h₀ : Nat.Prime p), ↑p ∣ n ↔ n ^ 2 % p = 0  := by
  intro n p h₀
  have hp : Prime (p : ℤ) := Nat.prime_iff_prime_int.mp h₀
  rw [← Int.dvd_iff_emod_eq_zero]
  exact ⟨fun h => dvd_pow h (by norm_num), hp.dvd_of_dvd_pow⟩

end Problems.Minif2f.numbertheory_prmdvsneqnsqmodpeq0
