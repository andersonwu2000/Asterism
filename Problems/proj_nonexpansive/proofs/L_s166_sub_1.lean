import Mathlib

namespace Problems.proj_nonexpansive

theorem s166_sub_1 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (u v : X) :
    |@inner ℝ X _ u v| ≤ ‖u‖ * ‖v‖ := by
  exact abs_real_inner_le_norm u v

end Problems.proj_nonexpansive
