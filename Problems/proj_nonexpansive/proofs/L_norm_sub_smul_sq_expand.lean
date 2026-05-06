-- norm_sub_smul_sq_expand: Closed by `norm_sub_sq_real` (expand the squared norm), `inner_smul_right` (pull scalar out of inner product), `norm_smul` + `Real.norm_eq_abs` + `sq_abs` (resolve `‖t • b‖² = t² * ‖b‖²`), then `ring` for the arithmetic.
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem norm_sub_smul_sq_expand {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b : X) (t : ℝ) :
    ‖a - t • b‖ ^ 2 = ‖a‖ ^ 2 - 2 * t * @inner ℝ _ _ a b + t ^ 2 * ‖b‖ ^ 2 := by
  rw [norm_sub_sq_real, inner_smul_right, norm_smul, Real.norm_eq_abs, mul_pow, sq_abs]
  ring

end Problems.proj_nonexpansive
