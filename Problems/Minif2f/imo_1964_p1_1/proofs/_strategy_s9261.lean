import Mathlib
import Problems.Minif2f.imo_1964_p1_1.Defs
import Problems.Minif2f.imo_1964_p1_1.proofs.L_mod_collapse
import Problems.Minif2f.imo_1964_p1_1.proofs.L_small_zero

namespace Problems.Minif2f.imo_1964_p1_1

-- Collapse 2^n mod 7 down to its representative on n % 3, then check k < 3.
-- mod_collapse: 7 ∣ 2^n - 1 ⇒ 7 ∣ 2^(n%3) - 1 (uses 2^3 ≡ 1 mod 7).
-- small_zero:   only k = 0 in {0,1,2} satisfies 7 ∣ 2^k - 1 (k=1,2 vacuous).
-- Combining gives n % 3 = 0, i.e. 3 ∣ n.
theorem s9261 : ∀ (n : ℕ) (h₀ : 7 ∣ 2 ^ n - 1), 3 ∣ n  := by
  intro n h₀
  have h_mod_collapse := mod_collapse n h₀
  have h2 : n % 3 = 0 :=
    small_zero (n % 3) (Nat.mod_lt n (by decide : (0:ℕ) < 3)) h_mod_collapse
  exact Nat.dvd_of_mod_eq_zero h2

end Problems.Minif2f.imo_1964_p1_1
