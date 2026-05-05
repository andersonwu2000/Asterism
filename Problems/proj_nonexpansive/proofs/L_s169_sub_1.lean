import Mathlib

namespace Problems.proj_nonexpansive

theorem s169_sub_1 (a b : ℝ)
    (h : ∀ t : ℝ, 0 < t → t < 1 → 2 * a ≤ t * b)
    (ε : ℝ) (hε : 0 < ε) :
    2 * a ≤ ε := by
  by_cases hb : b ≤ 0
  · -- b ≤ 0: t = 1/2 gives 2*a ≤ b/2 ≤ 0 < ε
    have h1 := h (1/2) (by norm_num) (by norm_num)
    nlinarith
  · simp only [not_le] at hb
    by_cases hbε : b ≤ 2 * ε
    · -- 0 < b ≤ 2ε: t = 1/2 gives 2*a ≤ b/2 ≤ ε
      have h1 := h (1/2) (by norm_num) (by norm_num)
      nlinarith
    · -- b > 2ε > ε: t = ε/b ∈ (0,1) and t*b = ε exactly
      simp only [not_le] at hbε
      have ht0 : (0 : ℝ) < ε / b := div_pos hε hb
      have ht1 : ε / b < 1 := by rw [div_lt_one hb]; linarith
      have h1 := h (ε / b) ht0 ht1
      have h2 : ε / b * b = ε := by field_simp [ne_of_gt hb]
      linarith

end Problems.proj_nonexpansive
