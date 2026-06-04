import Mathlib
import Problems.Minif2f.imo_1964_p1_1.Defs
import Problems.Minif2f.imo_1964_p1_1.proofs.L_period_iter

namespace Problems.Minif2f.imo_1964_p1_1

-- Iterate the period lemma 7 ∣ 2^(m+3) - 1 → 7 ∣ 2^m - 1 by induction on k.
-- period_iter: ∀ m k, 7 ∣ 2^(m + 3*k) - 1 → 7 ∣ 2^m - 1 (induct on k).
-- Apply with m = n%3, k = n/3, using Nat.mod_add_div : n%3 + 3*(n/3) = n.
theorem s9351 : ∀ (n : ℕ), 7 ∣ 2 ^ n - 1 → 7 ∣ 2 ^ (n % 3) - 1  := by
  intro n h
  have h' : 7 ∣ 2 ^ (n % 3 + 3 * (n / 3)) - 1 := by
    rw [Nat.mod_add_div]
    exact h
  exact period_iter (n % 3) (n / 3) h'

end Problems.Minif2f.imo_1964_p1_1
