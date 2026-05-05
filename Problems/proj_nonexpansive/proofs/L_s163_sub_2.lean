import Mathlib

namespace Problems.proj_nonexpansive

theorem s163_sub_2 (a b : ℝ) (hb : b ≥ 0)
    (h : ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * t * a ≤ t ^ 2 * b) : a ≤ 0 := by
  by_contra ha
  push_neg at ha
  by_cases hb_zero : b = 0
  · subst hb_zero
    nlinarith [h 1 one_pos le_rfl]
  · have hb_pos : 0 < b := lt_of_le_of_ne hb (Ne.symm hb_zero)
    have hab : 0 < a + b := by linarith
    have hr_pos : 0 < a / (a + b) := div_pos ha hab
    have hr_le1 : a / (a + b) ≤ 1 := by rw [div_le_one hab]; linarith
    have hkey := h (a / (a + b)) hr_pos hr_le1
    set r := a / (a + b) with hr_def
    have hdiv : r * (a + b) = a := by
      rw [hr_def]; exact div_mul_cancel₀ a (ne_of_gt hab)
    have hrb : r * b = a - r * a := by linarith [mul_add r a b]
    have hr2b : r ^ 2 * b = r * a - r ^ 2 * a := by
      have : r ^ 2 * b = r * (r * b) := by ring
      rw [this, hrb]; ring
    linarith [mul_pos hr_pos ha, mul_pos (pow_pos hr_pos 2) ha]

end Problems.proj_nonexpansive
