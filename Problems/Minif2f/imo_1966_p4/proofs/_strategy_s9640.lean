import Mathlib
import Problems.Minif2f.imo_1966_p4.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1966_p4

-- Direct telescoping: induction on n with `Finset.sum_Icc_succ_top` peeling off
-- the last term; simp normalizes Nat-subtracted 2^((n+1)-1) = 2^n and the
-- cancellation. Base case n=0 contradicted by h₁; n=1 reduces to a single Icc 1 1.
theorem s9640 : ∀ (n : ℕ) (x : ℝ)
    (h₀ : ∀ k : ℕ, 0 < k → ∀ m : ℤ, x ≠ m * π / 2 ^ k) (h₁ : 0 < n),
    (∑ k ∈ Finset.Icc 1 n, (1 / Real.tan (2 ^ (k-1) * x) - 1 / Real.tan (2 ^ k * x))) =
      1 / Real.tan x - 1 / Real.tan (2 ^ n * x) := by
  intro n x _ h₁
  induction n with
  | zero => omega
  | succ n ih =>
    by_cases hn : 0 < n
    · rw [Finset.sum_Icc_succ_top (by omega : 1 ≤ n + 1), ih hn]
      simp
    · interval_cases n
      simp [Finset.Icc_self]

end Problems.Minif2f.imo_1966_p4
