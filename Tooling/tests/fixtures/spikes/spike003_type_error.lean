import Mathlib
-- spike-003: type error test
theorem type_error_test (n : Nat) : n + 0 = n + 1 := by simp
