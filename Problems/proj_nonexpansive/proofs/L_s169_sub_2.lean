import Mathlib

namespace Problems.proj_nonexpansive

theorem s169_sub_2 (a b : ℝ)
    (h : ∀ t : ℝ, 0 < t → t < 1 → 2 * a ≤ t * b)
    (hall : ∀ ε : ℝ, 0 < ε → 2 * a ≤ ε) :
    a ≤ 0 := by
  by_contra ha
  simp only [not_le] at ha
  linarith [hall a ha]

end Problems.proj_nonexpansive
