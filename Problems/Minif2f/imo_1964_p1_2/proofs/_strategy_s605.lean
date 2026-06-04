import Mathlib
import Problems.Minif2f.imo_1964_p1_2.Defs

namespace Problems.Minif2f.imo_1964_p1_2

-- Direct proof: 2^n mod 7 cycles through {1,2,4}, so 2^n+1 mod 7 ∈ {2,3,5} ≠ 0.
-- Induct on n to get the invariant; combinator: `omega` finishes from `7 ∣ 2^n+1` + case.
theorem s605 : ∀ (n : ℕ), ¬7 ∣ 2 ^ n + 1  := by
  suffices h : ∀ n : ℕ, 2 ^ n % 7 = 1 ∨ 2 ^ n % 7 = 2 ∨ 2 ^ n % 7 = 4 by
    intro n hdvd
    have hcase := h n
    omega
  intro n
  induction n with
  | zero => left; decide
  | succ k ih =>
    rw [pow_succ]
    rcases ih with h | h | h <;> omega

end Problems.Minif2f.imo_1964_p1_2
