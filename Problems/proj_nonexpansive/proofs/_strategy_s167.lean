import Mathlib
import Problems.proj_nonexpansive.proofs.L_s167_sub_1
import Problems.proj_nonexpansive.proofs.L_s167_sub_2
import Problems.proj_nonexpansive.proofs.L_s167_sub_3

namespace Problems.proj_nonexpansive

theorem s167 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b p q : X)
    (h1 : @inner ℝ X _ (a - p) (b - a) ≥ 0)
    (h2 : @inner ℝ X _ (b - q) (a - b) ≥ 0) :
    @inner ℝ X _ ((p - q) - (a - b)) (a - b) ≥ 0  := by
  have h_vec := s167_sub_1 a b p q h1 h2
  have h_exp := s167_sub_2 a b p q h1 h2
  have h_sum := s167_sub_3 a b p q h1 h2
  rw [h_vec, h_exp]
  exact h_sum

end Problems.proj_nonexpansive
