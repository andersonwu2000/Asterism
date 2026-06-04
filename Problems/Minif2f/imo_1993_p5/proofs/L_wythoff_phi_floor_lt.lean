import Mathlib
namespace Problems.Minif2f.imo_1993_p5

-- wythoff_phi_floor_lt: floor of (k+1)·φ strictly less than (k+1)·φ via irrationality of √5;
-- if (k+1)·φ equaled its floor, then (k+1)·√5 would be an integer, making √5 rational.
theorem wythoff_phi_floor_lt :
    ∀ k : ℕ,
      ((⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ : ℤ) : ℝ)
        < ((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2) := by
  intro k
  apply lt_of_le_of_ne (Int.floor_le _)
  symm
  intro h
  -- Derive (k+1)*√5 = 2*⌊...⌋ - (k+1) (integer RHS)
  have hlinear : ((k : ℝ) + 1) * Real.sqrt 5 =
      2 * ↑⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ - ((k : ℝ) + 1) := by
    linear_combination 2 * h
  have hk1_pos : (0 : ℝ) < (k : ℝ) + 1 := by positivity
  -- √5 is irrational
  have hirr : Irrational (Real.sqrt 5) := by
    apply Nat.Prime.irrational_sqrt; norm_num
  -- Construct rational equal to √5, contradicting irrationality
  apply hirr
  let n : ℤ := ⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋
  refine ⟨(((2 * n - ((k : ℤ) + 1)) : ℤ) : ℚ) / (((k : ℤ) + 1) : ℚ), ?_⟩
  push_cast
  rw [div_eq_iff (by exact_mod_cast ne_of_gt hk1_pos)]
  linarith [mul_comm (Real.sqrt 5) ((k : ℝ) + 1)]

end Problems.Minif2f.imo_1993_p5
