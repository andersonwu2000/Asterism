import Mathlib
namespace Problems.Minif2f.amc12a_2009_p25

-- base_25: compute a 3..a 25 explicitly via recurrence, showing a 25 = 1 = a 1
-- Each step uses div_eq_iff (denominator ≠ 0 by nlinarith/field_simp with √3^2=3)
-- followed by field_simp [hsq3_ne] + nlinarith [hsq3_sq] to close polynomial goals.
-- Zero-numerator steps (a5, a17) use zero_div directly.
-- Trivial-denominator steps (a6, a7, a18, a19) use field_simp + ring.
-- set_option maxHeartbeats 800000 needed: 23-step chain exhausts the default budget.
set_option maxHeartbeats 800000 in
theorem base_25 :
    ∀ (a : ℕ → ℝ) (h₀ : a 1 = 1) (h₁ : a 2 = 1 / Real.sqrt 3)
      (h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1))),
      a 25 = a 1 := by
  intro a h₀ h₁ h₂
  have hsq3_pos : (0:ℝ) < Real.sqrt 3 := Real.sqrt_pos.mpr (by norm_num)
  have hsq3_ne : Real.sqrt 3 ≠ 0 := ne_of_gt hsq3_pos
  have hsq3_sq : Real.sqrt 3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  have h3 : a 3 = 2 + Real.sqrt 3 := by
    have hrec := h₂ 1 (by norm_num); norm_num at hrec; rw [h₀, h₁] at hrec; rw [hrec]
    have hd : (1:ℝ) - 1 * (1 / Real.sqrt 3) ≠ 0 := by
      intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h4 : a 4 = -(2 + Real.sqrt 3) := by
    have hrec := h₂ 2 (by norm_num); norm_num at hrec; rw [h₁, h3] at hrec; rw [hrec]
    have hd : (1:ℝ) - (1 / Real.sqrt 3) * (2 + Real.sqrt 3) ≠ 0 := by
      intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h5 : a 5 = 0 := by
    have hrec := h₂ 3 (by norm_num); norm_num at hrec; rw [h3, h4] at hrec; rw [hrec]
    rw [show (2:ℝ) + Real.sqrt 3 + -(2 + Real.sqrt 3) = 0 from by ring, zero_div]
  have h6 : a 6 = -(2 + Real.sqrt 3) := by
    have hrec := h₂ 4 (by norm_num); norm_num at hrec; rw [h4, h5] at hrec; rw [hrec]
    field_simp; ring
  have h7 : a 7 = -(2 + Real.sqrt 3) := by
    have hrec := h₂ 5 (by norm_num); norm_num at hrec; rw [h5, h6] at hrec; rw [hrec]
    field_simp; ring
  have h8 : a 8 = 1 / Real.sqrt 3 := by
    have hrec := h₂ 6 (by norm_num); norm_num at hrec; rw [h6, h7] at hrec; rw [hrec]
    have hd : (1:ℝ) - -(2 + Real.sqrt 3) * -(2 + Real.sqrt 3) ≠ 0 := by
      intro h; nlinarith [hsq3_sq, hsq3_pos]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h9 : a 9 = -1 := by
    have hrec := h₂ 7 (by norm_num); norm_num at hrec; rw [h7, h8] at hrec; rw [hrec]
    have hd : (1:ℝ) - -(2 + Real.sqrt 3) * (1 / Real.sqrt 3) ≠ 0 := by
      intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h10 : a 10 = Real.sqrt 3 - 2 := by
    have hrec := h₂ 8 (by norm_num); norm_num at hrec; rw [h8, h9] at hrec; rw [hrec]
    have hd : (1:ℝ) - (1 / Real.sqrt 3) * (-1) ≠ 0 := by
      intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h11 : a 11 = -Real.sqrt 3 := by
    have hrec := h₂ 9 (by norm_num); norm_num at hrec; rw [h9, h10] at hrec; rw [hrec]
    have hd : (1:ℝ) - (-1) * (Real.sqrt 3 - 2) ≠ 0 := by
      intro h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; nlinarith [hsq3_sq]
  have h12 : a 12 = -(2 + Real.sqrt 3) := by
    have hrec := h₂ 10 (by norm_num); norm_num at hrec; rw [h10, h11] at hrec; rw [hrec]
    have hd : (1:ℝ) - (Real.sqrt 3 - 2) * (-Real.sqrt 3) ≠ 0 := by
      intro h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; nlinarith [hsq3_sq]
  have h13 : a 13 = 1 := by
    have hrec := h₂ 11 (by norm_num); norm_num at hrec; rw [h11, h12] at hrec; rw [hrec]
    have hd : (1:ℝ) - (-Real.sqrt 3) * -(2 + Real.sqrt 3) ≠ 0 := by
      intro h; nlinarith [hsq3_sq, hsq3_pos]
    rw [div_eq_iff hd]; nlinarith [hsq3_sq]
  have h14 : a 14 = -(1 / Real.sqrt 3) := by
    have hrec := h₂ 12 (by norm_num); norm_num at hrec; rw [h12, h13] at hrec; rw [hrec]
    have hd : (1:ℝ) - -(2 + Real.sqrt 3) * 1 ≠ 0 := by
      intro h; nlinarith [hsq3_sq, hsq3_pos]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h15 : a 15 = 2 - Real.sqrt 3 := by
    have hrec := h₂ 13 (by norm_num); norm_num at hrec; rw [h13, h14] at hrec; rw [hrec]
    have hd : (1:ℝ) - 1 * -(1 / Real.sqrt 3) ≠ 0 := by
      intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h16 : a 16 = Real.sqrt 3 - 2 := by
    have hrec := h₂ 14 (by norm_num); norm_num at hrec; rw [h14, h15] at hrec; rw [hrec]
    have hd : (1:ℝ) - -(1 / Real.sqrt 3) * (2 - Real.sqrt 3) ≠ 0 := by
      intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h17 : a 17 = 0 := by
    have hrec := h₂ 15 (by norm_num); norm_num at hrec; rw [h15, h16] at hrec; rw [hrec]
    rw [show (2:ℝ) - Real.sqrt 3 + (Real.sqrt 3 - 2) = 0 from by ring, zero_div]
  have h18 : a 18 = Real.sqrt 3 - 2 := by
    have hrec := h₂ 16 (by norm_num); norm_num at hrec; rw [h16, h17] at hrec; rw [hrec]
    field_simp; ring
  have h19 : a 19 = Real.sqrt 3 - 2 := by
    have hrec := h₂ 17 (by norm_num); norm_num at hrec; rw [h17, h18] at hrec; rw [hrec]
    field_simp; ring
  have h20 : a 20 = -(1 / Real.sqrt 3) := by
    have hrec := h₂ 18 (by norm_num); norm_num at hrec; rw [h18, h19] at hrec; rw [hrec]
    have hd : (1:ℝ) - (Real.sqrt 3 - 2) * (Real.sqrt 3 - 2) ≠ 0 := by
      intro h; nlinarith [hsq3_sq, hsq3_pos]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h21 : a 21 = -1 := by
    have hrec := h₂ 19 (by norm_num); norm_num at hrec; rw [h19, h20] at hrec; rw [hrec]
    have hd : (1:ℝ) - (Real.sqrt 3 - 2) * -(1 / Real.sqrt 3) ≠ 0 := by
      intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h22 : a 22 = -(2 + Real.sqrt 3) := by
    have hrec := h₂ 20 (by norm_num); norm_num at hrec; rw [h20, h21] at hrec; rw [hrec]
    have hd : (1:ℝ) - -(1 / Real.sqrt 3) * (-1) ≠ 0 := by
      intro h; field_simp [hsq3_ne] at h; nlinarith [hsq3_sq]
    rw [div_eq_iff hd]; field_simp [hsq3_ne]; nlinarith [hsq3_sq]
  have h23 : a 23 = Real.sqrt 3 := by
    have hrec := h₂ 21 (by norm_num); norm_num at hrec; rw [h21, h22] at hrec; rw [hrec]
    have hd : (1:ℝ) - (-1) * -(2 + Real.sqrt 3) ≠ 0 := by
      intro h; nlinarith [hsq3_sq, hsq3_pos]
    rw [div_eq_iff hd]; nlinarith [hsq3_sq]
  have h24 : a 24 = Real.sqrt 3 - 2 := by
    have hrec := h₂ 22 (by norm_num); norm_num at hrec; rw [h22, h23] at hrec; rw [hrec]
    have hd : (1:ℝ) - -(2 + Real.sqrt 3) * Real.sqrt 3 ≠ 0 := by
      intro h; nlinarith [hsq3_sq, hsq3_pos]
    rw [div_eq_iff hd]; nlinarith [hsq3_sq]
  have h25 : a 25 = 1 := by
    have hrec := h₂ 23 (by norm_num); norm_num at hrec; rw [h23, h24] at hrec; rw [hrec]
    have hd : (1:ℝ) - Real.sqrt 3 * (Real.sqrt 3 - 2) ≠ 0 := by
      intro h; nlinarith [hsq3_sq, hsq3_pos]
    rw [div_eq_iff hd]; nlinarith [hsq3_sq]
  rw [h25, h₀]

end Problems.Minif2f.amc12a_2009_p25
