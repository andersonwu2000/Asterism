import Mathlib

namespace Problems.proj_nonexpansive

theorem s166_sub_2 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (u v : X) :
    @inner ℝ X _ u v ≤ |@inner ℝ X _ u v| := by grind

end Problems.proj_nonexpansive
