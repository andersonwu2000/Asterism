import Mathlib

namespace Problems.Minif2f.imo_1993_p5

-- Direct: F = ⌊(k+1)·φ⌋ satisfies F > (k+1)·φ - 1 by `Int.sub_one_lt_floor`.
-- Multiply that bound by (φ-1) > 0 to get F·(φ-1) ≥ ((k+1)·φ - 1)·(φ-1) = k + 2 - φ ≥ k
-- (using φ² = φ + 1, i.e. sqrt 5 * sqrt 5 = 5, and φ ≤ 2 via sqrt 5 ≤ 3).
theorem s9952 :
    ∀ k : ℕ,
      ((⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ : ℤ) : ℝ) + (k : ℝ)
        ≤ (⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ : ℝ)
            * ((1 + Real.sqrt 5) / 2)  := by
  intro k
  have h_sqrt_sq : Real.sqrt 5 * Real.sqrt 5 = 5 :=
    Real.mul_self_sqrt (by norm_num : (0:ℝ) ≤ 5)
  have h_sqrt_nn : 0 ≤ Real.sqrt 5 := Real.sqrt_nonneg 5
  have h_sqrt_le : Real.sqrt 5 ≤ 3 := by nlinarith [h_sqrt_sq, h_sqrt_nn]
  have h_phi_pos : (0:ℝ) < (1 + Real.sqrt 5)/2 - 1 := by nlinarith [h_sqrt_sq, h_sqrt_nn]
  have hfloor : ((k:ℝ)+1) * ((1 + Real.sqrt 5)/2) - 1 < (⌊((k:ℝ)+1) * ((1 + Real.sqrt 5)/2)⌋ : ℝ) :=
    Int.sub_one_lt_floor _
  have hmul : (((k:ℝ)+1) * ((1 + Real.sqrt 5)/2) - 1) * ((1 + Real.sqrt 5)/2 - 1)
              ≤ (⌊((k:ℝ)+1) * ((1 + Real.sqrt 5)/2)⌋ : ℝ) * ((1 + Real.sqrt 5)/2 - 1) := by
    apply mul_le_mul_of_nonneg_right (le_of_lt hfloor) (le_of_lt h_phi_pos)
  nlinarith [hmul, h_sqrt_sq, h_sqrt_nn, h_sqrt_le, h_phi_pos]

end Problems.Minif2f.imo_1993_p5
