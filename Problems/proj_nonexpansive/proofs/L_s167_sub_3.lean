import Mathlib

namespace Problems.proj_nonexpansive

theorem s167_sub_3 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b p q : X)
    (h1 : @inner ℝ X _ (a - p) (b - a) ≥ 0)
    (h2 : @inner ℝ X _ (b - q) (a - b) ≥ 0) :
    @inner ℝ X _ (b - q) (a - b) + @inner ℝ X _ (a - p) (b - a) ≥ 0 := by linarith

end Problems.proj_nonexpansive
