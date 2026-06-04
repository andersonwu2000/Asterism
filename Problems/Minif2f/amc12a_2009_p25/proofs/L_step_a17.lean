import Mathlib
namespace Problems.Minif2f.amc12a_2009_p25

-- step_a17: a 17 = 0 given milestones a 13 = 1, a 14 = -1/√3 via the tan-addition recurrence;
-- a 15 = (√3-1)/(√3+1), a 16 = -a 15 (algebraically from s²=3), so numerator of a 17 vanishes.
theorem step_a17 :
    ∀ (a : ℕ → ℝ) (_h₀ : a 1 = 1) (_h₁ : a 2 = 1 / Real.sqrt 3)
      (_h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1)))
      (_h13 : a 13 = 1) (_h14 : a 14 = -(1 / Real.sqrt 3)),
      a 17 = 0 := by
  intro a h₀ h₁ h₂ h13 h14
  have hs2 : Real.sqrt 3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  have hs_pos : (0 : ℝ) < Real.sqrt 3 := Real.sqrt_pos.mpr (by norm_num)
  have hs_ne : Real.sqrt 3 ≠ 0 := hs_pos.ne'
  have h15eq : a 15 = (a 13 + a 14) / (1 - a 13 * a 14) := h₂ 13 (by norm_num)
  have h16eq : a 16 = (a 14 + a 15) / (1 - a 14 * a 15) := h₂ 14 (by norm_num)
  have h17eq : a 17 = (a 15 + a 16) / (1 - a 15 * a 16) := h₂ 15 (by norm_num)
  have hs1 : Real.sqrt 3 + 1 ≠ 0 := by positivity
  have ha15 : a 15 = (Real.sqrt 3 - 1) / (Real.sqrt 3 + 1) := by
    have eq1 : (1 : ℝ) + -(1 / Real.sqrt 3) = (Real.sqrt 3 - 1) / Real.sqrt 3 := by
      field_simp; ring
    have eq2 : (1 : ℝ) - 1 * -(1 / Real.sqrt 3) = (Real.sqrt 3 + 1) / Real.sqrt 3 := by
      field_simp; ring
    rw [h15eq, h13, h14, eq1, eq2]
    field_simp [hs_ne]
  have ha16 : a 16 = -((Real.sqrt 3 - 1) / (Real.sqrt 3 + 1)) := by
    rw [h16eq, h14, ha15]
    have hd2_val : (1 : ℝ) - -(1 / Real.sqrt 3) * ((Real.sqrt 3 - 1) / (Real.sqrt 3 + 1)) =
                   2 / Real.sqrt 3 := by
      field_simp [hs_ne, hs1]
      nlinarith [hs2]
    rw [hd2_val]
    field_simp [hs_ne, hs1]
    nlinarith [hs2]
  rw [h17eq, ha15, ha16]
  ring

end Problems.Minif2f.amc12a_2009_p25
