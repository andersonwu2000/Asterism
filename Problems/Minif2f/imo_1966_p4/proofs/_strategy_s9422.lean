import Mathlib
import Problems.Minif2f.imo_1966_p4.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1966_p4

-- Direct telescoping sum proof — pure algebraic identity (h₀ and h₁ unused).
-- Induction on n: base n=0 closes by `simp` (empty sum on the left, 0 on right since 2^0*x=x).
-- Step uses `Finset.sum_Icc_succ_top` to peel the last term off Icc 1 (m+1), then either
-- handles m=0 directly or applies the IH and closes with `simp` (telescoping cancellation).
theorem s9422 : ∀ (n : ℕ) (x : ℝ) (h₀ : ∀ k : ℕ, 0 < k → ∀ m : ℤ, x ≠ m * π / 2 ^ k) (h₁ : 0 < n), (∑ k ∈ Finset.Icc 1 n, (1 / Real.tan (2 ^ (k-1) * x) - 1 / Real.tan (2 ^ k * x))) = 1 / Real.tan x - 1 / Real.tan (2 ^ n * x)  := by
  intro n x _ _
  induction n with
  | zero => simp
  | succ m ih =>
    rw [Finset.sum_Icc_succ_top (by omega : 1 ≤ m + 1)]
    by_cases hm : m = 0
    · subst hm; simp
    · rw [ih (Nat.pos_of_ne_zero hm)]
      simp
end Problems.Minif2f.imo_1966_p4
