import Mathlib
-- spike-003: multiple sorry case (more realistic proof attempt)
theorem sorry_multi_1 (n : Nat) : n + n = 2 * n := by
  sorry

theorem sorry_multi_2 (n : Nat) : n * 0 = 0 := by
  sorry

-- Also test: sorry in proof term (not tactic)
theorem sorry_term : 1 = 2 := sorry
