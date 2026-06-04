import Mathlib
namespace Problems.Minif2f.amc12a_2009_p25

-- step_a8_a9: cascade recurrence from a5=0 through a6,a7 (both -(2+√3)) to
-- reach a8=1/√3 and a9=-1; denominators verified nonzero via nlinarith/positivity
theorem step_a8_a9 :
    ∀ (a : ℕ → ℝ) (_h₀ : a 1 = 1) (_h₁ : a 2 = 1 / Real.sqrt 3)
      (_h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1)))
      (_h4 : a 4 = -(2 + Real.sqrt 3)) (_h5 : a 5 = 0),
      a 8 = 1 / Real.sqrt 3 ∧ a 9 = -1 := by
  intro a h₀ h₁ h₂ h4 h5
  have sqrt3_pos : (0 : ℝ) < Real.sqrt 3 := Real.sqrt_pos.mpr (by norm_num)
  have sqrt3_ne : Real.sqrt 3 ≠ 0 := ne_of_gt sqrt3_pos
  have sqrt3_sq : Real.sqrt 3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  have h6 : a 6 = -(2 + Real.sqrt 3) := by
    have eq6 := h₂ 4 (by norm_num)
    norm_num at eq6
    rw [h4, h5] at eq6
    rw [eq6]
    ring
  have h7 : a 7 = -(2 + Real.sqrt 3) := by
    have eq7 := h₂ 5 (by norm_num)
    norm_num at eq7
    rw [h5, h6] at eq7
    rw [eq7]
    ring
  have h8 : a 8 = 1 / Real.sqrt 3 := by
    have eq8 := h₂ 6 (by norm_num)
    norm_num at eq8
    rw [h6, h7] at eq8
    rw [eq8]
    have hd8 : (1 : ℝ) - -(2 + Real.sqrt 3) * -(2 + Real.sqrt 3) ≠ 0 := by
      nlinarith [sqrt3_sq, sqrt3_pos]
    rw [div_eq_div_iff hd8 sqrt3_ne]
    nlinarith [sqrt3_sq, sqrt3_pos]
  have h9 : a 9 = -1 := by
    have eq9 := h₂ 7 (by norm_num)
    norm_num at eq9
    rw [h7, h8] at eq9
    rw [eq9]
    have hd9 : (1 : ℝ) - -(2 + Real.sqrt 3) * (1 / Real.sqrt 3) ≠ 0 := by
      apply ne_of_gt
      have h1 : (0 : ℝ) < (2 + Real.sqrt 3) / Real.sqrt 3 := by positivity
      have h2 : (1 : ℝ) - -(2 + Real.sqrt 3) * (1 / Real.sqrt 3) =
                1 + (2 + Real.sqrt 3) / Real.sqrt 3 := by ring
      linarith
    rw [div_eq_iff hd9]
    field_simp [sqrt3_ne]
    nlinarith [sqrt3_sq, Real.mul_self_sqrt (show (3:ℝ) ≥ 0 by norm_num)]
  exact ⟨h8, h9⟩

end Problems.Minif2f.amc12a_2009_p25
