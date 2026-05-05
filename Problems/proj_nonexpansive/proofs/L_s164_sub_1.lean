import Mathlib

namespace Problems.proj_nonexpansive

theorem s164_sub_1 {X : Type*} [NormedAddCommGroup X]
    (u v : X) (hu : ‖u‖ = 0) :
    ‖u‖ ≤ ‖v‖ := by simp_all

end Problems.proj_nonexpansive
