-- norm_sq_ineq: proved by hint: gcongr
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem norm_sq_ineq {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b : X) (t : ℝ) (ht : 0 < t) (h : ‖a‖ ≤ ‖a - t • b‖) :
    ‖a‖ ^ 2 ≤ ‖a - t • b‖ ^ 2 := by gcongr

end Problems.proj_nonexpansive
