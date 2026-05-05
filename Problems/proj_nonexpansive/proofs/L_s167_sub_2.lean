import Mathlib

namespace Problems.proj_nonexpansive

theorem s167_sub_2 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b p q : X)
    (h1 : @inner ℝ X _ (a - p) (b - a) ≥ 0)
    (h2 : @inner ℝ X _ (b - q) (a - b) ≥ 0) :
    @inner ℝ X _ ((b - q) - (a - p)) (a - b) =
    @inner ℝ X _ (b - q) (a - b) + @inner ℝ X _ (a - p) (b - a) := by
  have h : @inner ℝ X _ (a - p) (b - a) = -@inner ℝ X _ (a - p) (a - b) := by
    rw [show b - a = -(a - b) from by abel]
    exact inner_neg_right (a - p) (a - b)
  rw [inner_sub_left]
  linarith

end Problems.proj_nonexpansive
