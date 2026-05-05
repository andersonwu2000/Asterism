import Mathlib

namespace Problems.proj_nonexpansive

theorem s164_sub_2 {X : Type*} [NormedAddCommGroup X]
    (u v : X) (h : ‖u‖ ^ 2 ≤ ‖v‖ * ‖u‖) (hu : 0 < ‖u‖) :
    ‖u‖ ≤ ‖v‖ := by nlinarith

end Problems.proj_nonexpansive
