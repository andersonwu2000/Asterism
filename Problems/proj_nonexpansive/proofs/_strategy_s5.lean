import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_norm_sq_ineq
import Problems.proj_nonexpansive.proofs.L_norm_sub_smul_sq_expand

namespace Problems.proj_nonexpansive

theorem s5 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b : X) (t : ℝ) (ht : 0 < t) (h : ‖a‖ ≤ ‖a - t • b‖) :
    2 * t * @inner ℝ _ _ a b ≤ t ^ 2 * ‖b‖ ^ 2  := by
  have h1 : ‖a‖ ^ 2 ≤ ‖a - t • b‖ ^ 2 := norm_sq_ineq a b t ht h
  have h2 : ‖a - t • b‖ ^ 2 = ‖a‖ ^ 2 - 2 * t * @inner ℝ _ _ a b + t ^ 2 * ‖b‖ ^ 2 :=
    norm_sub_smul_sq_expand a b t
  linarith

end Problems.proj_nonexpansive
