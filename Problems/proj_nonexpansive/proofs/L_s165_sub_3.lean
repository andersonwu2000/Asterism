import Mathlib

namespace Problems.proj_nonexpansive

theorem s165_sub_3 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (u v : X)
    (h : @inner ℝ X _ (u - v) v ≥ 0) :
    ‖v‖ ^ 2 ≤ @inner ℝ X _ u v := by
  have h1 : @inner ℝ X _ (u - v) v = @inner ℝ X _ u v - @inner ℝ X _ v v :=
    inner_sub_left u v v
  have h2 : @inner ℝ X _ v v = ‖v‖ ^ 2 := real_inner_self_eq_norm_sq v
  linarith

end Problems.proj_nonexpansive
