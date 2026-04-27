import Mathlib
-- spike-003: unsolved goals (wrong tactic)
theorem unsolved_test (n : Nat) : n + 0 = n := by
  ring_nf
  -- intentionally left unsolved after ring_nf
