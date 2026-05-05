import Mathlib
import Problems.proj_nonexpansive.proofs.L_s166_sub_1
import Problems.proj_nonexpansive.proofs.L_s166_sub_2

namespace Problems.proj_nonexpansive

theorem s166 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (u v : X) :
    @inner ℝ X _ u v ≤ ‖u‖ * ‖v‖  := by
  have h1 : |@inner ℝ X _ u v| ≤ ‖u‖ * ‖v‖ := s166_sub_1 u v
  have h2 : @inner ℝ X _ u v ≤ |@inner ℝ X _ u v| := s166_sub_2 u v
  linarith

end Problems.proj_nonexpansive
