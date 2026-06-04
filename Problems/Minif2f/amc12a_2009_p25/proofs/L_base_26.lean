import Mathlib

namespace Problems.Minif2f.amc12a_2009_p25

-- base_26: 24-step recurrence cascade showing a 26 = 1/√3 = a 2;
-- each step computes the next term via the tan-addition recurrence,
-- with explicit denominator nonzero witnesses using nlinarith/positivity.
set_option maxHeartbeats 2000000 in
-- 24-step cascade: each recurrence step uses field_simp/nlinarith on √3 polynomial goals
theorem base_26 :
    ∀ (a : ℕ → ℝ) (_h₀ : a 1 = 1) (_h₁ : a 2 = 1 / Real.sqrt 3)
      (_h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1))),
      a 26 = a 2 := by
  intro a h₀ h₁ h₂
  have hs : Real.sqrt 3 * Real.sqrt 3 = 3 := Real.mul_self_sqrt (by norm_num)
  have hne : Real.sqrt 3 ≠ 0 := Real.sqrt_ne_zero'.mpr (by norm_num)
  have hpos : (0 : ℝ) < Real.sqrt 3 := Real.sqrt_pos.mpr (by norm_num)
  have h3 : a 3 = 2 + Real.sqrt 3 := by
    have := h₂ 1 (by norm_num); norm_num at this; rw [h₀, h₁] at this; rw [this]
    have hd : (1 : ℝ) - 1 * (1 / Real.sqrt 3) ≠ 0 := by
      have : 1 / Real.sqrt 3 < 1 := (div_lt_one hpos).mpr (by nlinarith [hs])
      linarith
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h4 : a 4 = -(2 + Real.sqrt 3) := by
    have := h₂ 2 (by norm_num); norm_num at this; rw [h₁, h3] at this; rw [this]
    have hd : (1 : ℝ) - 1 / Real.sqrt 3 * (2 + Real.sqrt 3) ≠ 0 := by
      have : 1 / Real.sqrt 3 * (2 + Real.sqrt 3) = 2 / Real.sqrt 3 + 1 := by field_simp [hne]
      have hpos2 : (0 : ℝ) < 2 / Real.sqrt 3 := div_pos (by norm_num) hpos
      linarith
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h5 : a 5 = 0 := by
    have := h₂ 3 (by norm_num); norm_num at this; rw [h3, h4] at this; rw [this]; ring
  have h6 : a 6 = -(2 + Real.sqrt 3) := by
    have := h₂ 4 (by norm_num); norm_num at this; rw [h4, h5] at this; rw [this]; ring
  have h7 : a 7 = -(2 + Real.sqrt 3) := by
    have := h₂ 5 (by norm_num); norm_num at this; rw [h5, h6] at this; rw [this]; ring
  have h8 : a 8 = 1 / Real.sqrt 3 := by
    have := h₂ 6 (by norm_num); norm_num at this; rw [h6, h7] at this; rw [this]
    have hd : (1 : ℝ) - -(2 + Real.sqrt 3) * -(2 + Real.sqrt 3) ≠ 0 := by nlinarith [hs]
    rw [div_eq_div_iff hd hne]; nlinarith [hs]
  have h9 : a 9 = -1 := by
    have := h₂ 7 (by norm_num); norm_num at this; rw [h7, h8] at this; rw [this]
    have hd : (1 : ℝ) - -(2 + Real.sqrt 3) * (1 / Real.sqrt 3) ≠ 0 := by
      apply ne_of_gt
      have h1 : (0 : ℝ) < (2 + Real.sqrt 3) / Real.sqrt 3 := by positivity
      have h2 : (1 : ℝ) - -(2 + Real.sqrt 3) * (1 / Real.sqrt 3) =
                1 + (2 + Real.sqrt 3) / Real.sqrt 3 := by ring
      linarith
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h10 : a 10 = Real.sqrt 3 - 2 := by
    have := h₂ 8 (by norm_num); norm_num at this; rw [h8, h9] at this; rw [this]
    have hd : (1 : ℝ) - 1 / Real.sqrt 3 * -1 ≠ 0 := by
      have : (1 : ℝ) - 1 / Real.sqrt 3 * -1 = 1 + 1 / Real.sqrt 3 := by ring
      rw [this]; positivity
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h11 : a 11 = -Real.sqrt 3 := by
    have := h₂ 9 (by norm_num); norm_num at this; rw [h9, h10] at this; rw [this]
    have hd : (1 : ℝ) - -1 * (Real.sqrt 3 - 2) ≠ 0 := by nlinarith
    rw [div_eq_iff hd]; ring_nf; nlinarith [hs]
  have h12 : a 12 = -(2 + Real.sqrt 3) := by
    have := h₂ 10 (by norm_num); norm_num at this; rw [h10, h11] at this; rw [this]
    have hd : (1 : ℝ) - (Real.sqrt 3 - 2) * -Real.sqrt 3 ≠ 0 := by nlinarith [hs]
    rw [div_eq_iff hd]; ring_nf; nlinarith [hs]
  have h13 : a 13 = 1 := by
    have := h₂ 11 (by norm_num); norm_num at this; rw [h11, h12] at this; rw [this]
    have hd : (1 : ℝ) - -Real.sqrt 3 * -(2 + Real.sqrt 3) ≠ 0 := by nlinarith [hs]
    rw [div_eq_iff hd]; ring_nf; nlinarith [hs]
  have h14 : a 14 = -(1 / Real.sqrt 3) := by
    have := h₂ 12 (by norm_num); norm_num at this; rw [h12, h13] at this; rw [this]
    have hd : (1 : ℝ) - -(2 + Real.sqrt 3) * 1 ≠ 0 := by nlinarith
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h15 : a 15 = 2 - Real.sqrt 3 := by
    have := h₂ 13 (by norm_num); norm_num at this; rw [h13, h14] at this; rw [this]
    have hd : (1 : ℝ) - 1 * -(1 / Real.sqrt 3) ≠ 0 := by
      have : (1 : ℝ) - 1 * -(1 / Real.sqrt 3) = 1 + 1 / Real.sqrt 3 := by ring
      rw [this]; positivity
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h16 : a 16 = Real.sqrt 3 - 2 := by
    have := h₂ 14 (by norm_num); norm_num at this; rw [h14, h15] at this; rw [this]
    have hd : (1 : ℝ) - -(1 / Real.sqrt 3) * (2 - Real.sqrt 3) ≠ 0 := by
      have : (1 : ℝ) - -(1 / Real.sqrt 3) * (2 - Real.sqrt 3) = 2 / Real.sqrt 3 := by
        field_simp [hne]; ring
      rw [this]; positivity
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h17 : a 17 = 0 := by
    have := h₂ 15 (by norm_num); norm_num at this; rw [h15, h16] at this; rw [this]; ring
  have h18 : a 18 = Real.sqrt 3 - 2 := by
    have := h₂ 16 (by norm_num); norm_num at this; rw [h16, h17] at this; rw [this]; ring
  have h19 : a 19 = Real.sqrt 3 - 2 := by
    have := h₂ 17 (by norm_num); norm_num at this; rw [h17, h18] at this; rw [this]; ring
  have h20 : a 20 = -(1 / Real.sqrt 3) := by
    have := h₂ 18 (by norm_num); norm_num at this; rw [h18, h19] at this; rw [this]
    have hd : (1 : ℝ) - (Real.sqrt 3 - 2) * (Real.sqrt 3 - 2) ≠ 0 := by nlinarith [hs]
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h21 : a 21 = -1 := by
    have := h₂ 19 (by norm_num); norm_num at this; rw [h19, h20] at this; rw [this]
    have hd : (1 : ℝ) - (Real.sqrt 3 - 2) * -(1 / Real.sqrt 3) ≠ 0 := by
      have heq : (1 : ℝ) - (Real.sqrt 3 - 2) * -(1 / Real.sqrt 3) =
                 (2 * Real.sqrt 3 - 2) / Real.sqrt 3 := by field_simp [hne]; ring
      rw [heq]; apply div_ne_zero _ hne; nlinarith [hs]
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h22 : a 22 = -(2 + Real.sqrt 3) := by
    have := h₂ 20 (by norm_num); norm_num at this; rw [h20, h21] at this; rw [this]
    have hd : (1 : ℝ) - -(1 / Real.sqrt 3) * -1 ≠ 0 := by
      have : (1 : ℝ) - -(1 / Real.sqrt 3) * -1 = 1 - 1 / Real.sqrt 3 := by ring
      rw [this]
      have : 1 / Real.sqrt 3 < 1 := (div_lt_one hpos).mpr (by nlinarith [hs])
      linarith
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  have h23 : a 23 = Real.sqrt 3 := by
    have := h₂ 21 (by norm_num); norm_num at this; rw [h21, h22] at this; rw [this]
    have hd : (1 : ℝ) - -1 * -(2 + Real.sqrt 3) ≠ 0 := by
      have : (1 : ℝ) - -1 * -(2 + Real.sqrt 3) = -(1 + Real.sqrt 3) := by ring
      rw [this]; linarith
    rw [div_eq_iff hd]; ring_nf; nlinarith [hs]
  have h24 : a 24 = Real.sqrt 3 - 2 := by
    have := h₂ 22 (by norm_num); norm_num at this; rw [h22, h23] at this; rw [this]
    have hd : (1 : ℝ) - -(2 + Real.sqrt 3) * Real.sqrt 3 ≠ 0 := by nlinarith [hs]
    rw [div_eq_iff hd]; ring_nf; nlinarith [hs]
  have h25 : a 25 = 1 := by
    have := h₂ 23 (by norm_num); norm_num at this; rw [h23, h24] at this; rw [this]
    have hd : (1 : ℝ) - Real.sqrt 3 * (Real.sqrt 3 - 2) ≠ 0 := by nlinarith [hs]
    rw [div_eq_iff hd]; ring_nf; nlinarith [hs]
  have h26 : a 26 = 1 / Real.sqrt 3 := by
    have := h₂ 24 (by norm_num); norm_num at this; rw [h24, h25] at this; rw [this]
    have hd : (1 : ℝ) - (Real.sqrt 3 - 2) * 1 ≠ 0 := by nlinarith [hs]
    rw [div_eq_iff hd]; field_simp [hne]; nlinarith [hs]
  rw [h26, h₁]

end Problems.Minif2f.amc12a_2009_p25
