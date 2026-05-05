import Mathlib
import Problems.proj_nonexpansive.proofs.L_s164_sub_1
import Problems.proj_nonexpansive.proofs.L_s164_sub_2

namespace Problems.proj_nonexpansive

theorem s164 {X : Type*} [NormedAddCommGroup X]
    (u v : X) (h : ‖u‖ ^ 2 ≤ ‖v‖ * ‖u‖) :
    ‖u‖ ≤ ‖v‖  := by
  by_cases hu : ‖u‖ = 0
  · exact s164_sub_1 u v hu
  · have hu_pos : 0 < ‖u‖ := lt_of_le_of_ne (norm_nonneg u) (Ne.symm hu)
    exact s164_sub_2 u v h hu_pos

end Problems.proj_nonexpansive
