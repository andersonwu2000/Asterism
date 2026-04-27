import Mathlib
-- Case: unknown tactic
theorem unknown_tactic_test (n : Nat) : n + 0 = n := by
  completely_made_up_tactic
