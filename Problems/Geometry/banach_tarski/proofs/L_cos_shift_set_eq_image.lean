import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem cos_shift_set_eq_image (ψ : ℝ) :
    {φ : ℝ | Real.cos (φ + ψ) = 0}
      = (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0} := by aesop

end Problems.Geometry.banach_tarski
