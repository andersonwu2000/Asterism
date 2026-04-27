-- spike-003: type error test (no Mathlib, faster)
theorem type_error_test (n : Nat) : n + 0 = n + 1 := by simp
