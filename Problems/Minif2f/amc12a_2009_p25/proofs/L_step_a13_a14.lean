import Mathlib
namespace Problems.Minif2f.amc12a_2009_p25

-- step_a13_a14: cascade recurrence from (a8, a9) through (a10–a12) to reach a13=1, a14=-1/√3
-- Each step uses div_eq_iff to clear the denominator, then field_simp + nlinarith with √3*√3=3.
theorem step_a13_a14 :
    ∀ (a : ℕ → ℝ) (_h₀ : a 1 = 1) (_h₁ : a 2 = 1 / Real.sqrt 3)
      (_h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1)))
      (_h8 : a 8 = 1 / Real.sqrt 3) (_h9 : a 9 = -1),
      a 13 = 1 ∧ a 14 = -(1 / Real.sqrt 3) := by
  intro a h₀ h₁ h₂ h8 h9
  have hsq3 : Real.sqrt 3 > 0 := Real.sqrt_pos.mpr (by norm_num)
  have hsq3_ne : Real.sqrt 3 ≠ 0 := ne_of_gt hsq3
  have hsq3_sq : Real.sqrt 3 * Real.sqrt 3 = 3 := Real.mul_self_sqrt (by norm_num)
  have h10 : a 10 = Real.sqrt 3 - 2 := by
    have hrec := h₂ 8 (by norm_num); norm_num at hrec
    rw [h8, h9] at hrec; rw [hrec]
    have hd : 1 - 1 / Real.sqrt 3 * -1 ≠ 0 := by
      have : 1 - 1 / Real.sqrt 3 * -1 = 1 + 1 / Real.sqrt 3 := by ring
      rw [this]; positivity
    rw [div_eq_iff hd]
    field_simp [hsq3_ne]
    nlinarith [hsq3_sq]
  have h11 : a 11 = -Real.sqrt 3 := by
    have hrec := h₂ 9 (by norm_num); norm_num at hrec
    rw [h9, h10] at hrec; rw [hrec]
    have hd : 1 - -1 * (Real.sqrt 3 - 2) ≠ 0 := by nlinarith
    rw [div_eq_iff hd]
    ring_nf; nlinarith [hsq3_sq]
  have h12 : a 12 = -(2 + Real.sqrt 3) := by
    have hrec := h₂ 10 (by norm_num); norm_num at hrec
    rw [h10, h11] at hrec; rw [hrec]
    have hd : 1 - (Real.sqrt 3 - 2) * -Real.sqrt 3 ≠ 0 := by nlinarith [hsq3_sq]
    rw [div_eq_iff hd]
    ring_nf; nlinarith [hsq3_sq]
  have h13 : a 13 = 1 := by
    have hrec := h₂ 11 (by norm_num); norm_num at hrec
    rw [h11, h12] at hrec; rw [hrec]
    have hd : 1 - -Real.sqrt 3 * -(2 + Real.sqrt 3) ≠ 0 := by nlinarith [hsq3_sq]
    rw [div_eq_iff hd]
    ring_nf; nlinarith [hsq3_sq]
  have h14 : a 14 = -(1 / Real.sqrt 3) := by
    have hrec := h₂ 12 (by norm_num); norm_num at hrec
    rw [h12, h13] at hrec; rw [hrec]
    have hd : 1 - -(2 + Real.sqrt 3) * 1 ≠ 0 := by nlinarith
    rw [div_eq_iff hd]
    field_simp [hsq3_ne]
    nlinarith [hsq3_sq]
  exact ⟨h13, h14⟩

end Problems.Minif2f.amc12a_2009_p25
