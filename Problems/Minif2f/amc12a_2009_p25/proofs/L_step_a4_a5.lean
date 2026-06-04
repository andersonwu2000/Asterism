import Mathlib

namespace Problems.Minif2f.amc12a_2009_p25

-- step_a4_a5: compute a(3)=2+√3, a(4)=-(2+√3), a(5)=0 from recurrence
-- Uses div_eq_iff + field_simp to clear denominators, nlinarith with √3*√3=3
theorem step_a4_a5 :
    ∀ (a : ℕ → ℝ) (_h₀ : a 1 = 1) (_h₁ : a 2 = 1 / Real.sqrt 3)
      (_h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1))),
      a 4 = -(2 + Real.sqrt 3) ∧ a 5 = 0 := by
  intro a h₀ h₁ h₂
  have sqrt3_pos : (0 : ℝ) < Real.sqrt 3 := Real.sqrt_pos.mpr (by norm_num)
  have sqrt3_ne : Real.sqrt 3 ≠ 0 := ne_of_gt sqrt3_pos
  have sqrt3_mul : Real.sqrt 3 * Real.sqrt 3 = 3 := Real.mul_self_sqrt (by norm_num)
  have sqrt3_gt1 : 1 < Real.sqrt 3 := by nlinarith [sqrt3_mul]
  have h3 : a 3 = 2 + Real.sqrt 3 := by
    have eq3 := h₂ 1 (by norm_num)
    norm_num at eq3
    rw [h₀, h₁] at eq3; rw [eq3]
    have den_ne : (1 : ℝ) - 1 * (1 / Real.sqrt 3) ≠ 0 := by
      have : 1 / Real.sqrt 3 < 1 := (div_lt_one sqrt3_pos).mpr sqrt3_gt1
      linarith
    rw [div_eq_iff den_ne]
    field_simp [sqrt3_ne]
    nlinarith [sqrt3_mul, sqrt3_pos]
  have h4 : a 4 = -(2 + Real.sqrt 3) := by
    have eq4 := h₂ 2 (by norm_num)
    norm_num at eq4
    rw [h₁, h3] at eq4; rw [eq4]
    have den_ne : (1 : ℝ) - 1 / Real.sqrt 3 * (2 + Real.sqrt 3) ≠ 0 := by
      have h : 1 / Real.sqrt 3 * (2 + Real.sqrt 3) = 2 / Real.sqrt 3 + 1 := by
        field_simp [sqrt3_ne]
      have hpos : (0 : ℝ) < 2 / Real.sqrt 3 := div_pos (by norm_num) sqrt3_pos
      have hlt : 1 - 1 / Real.sqrt 3 * (2 + Real.sqrt 3) < 0 := by linarith
      exact ne_of_lt hlt
    rw [div_eq_iff den_ne]
    field_simp [sqrt3_ne]
    nlinarith [sqrt3_mul, sqrt3_pos]
  have h5 : a 5 = 0 := by
    have eq5 := h₂ 3 (by norm_num)
    norm_num at eq5
    rw [h3, h4] at eq5; rw [eq5]
    simp
  exact ⟨h4, h5⟩

end Problems.Minif2f.amc12a_2009_p25
