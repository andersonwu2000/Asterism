import Mathlib

-- spike-002: demo theorem for P1 - what axioms does add_zero_simple use?
theorem add_zero_simple (n : Nat) : n + 0 = n := by simp
#print axioms add_zero_simple

-- Alternative proofs and their axioms
theorem add_zero_rfl (n : Nat) : n + 0 = n := Nat.add_zero n
#print axioms add_zero_rfl

-- theorem using ring
theorem mul_one_ring (n : Nat) : n * 1 = n := by ring
#print axioms mul_one_ring

-- theorem using omega (linear arithmetic)
theorem le_add_right' (n m : Nat) : n ≤ n + m := by omega
#print axioms le_add_right'
