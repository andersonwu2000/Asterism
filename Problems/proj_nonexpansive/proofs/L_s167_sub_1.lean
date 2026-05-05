import Mathlib

namespace Problems.proj_nonexpansive

theorem s167_sub_1 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b p q : X)
    (h1 : @inner ℝ X _ (a - p) (b - a) ≥ 0)
    (h2 : @inner ℝ X _ (b - q) (a - b) ≥ 0) :
    (p - q) - (a - b) = (b - q) - (a - p) := by grind

end Problems.proj_nonexpansive
