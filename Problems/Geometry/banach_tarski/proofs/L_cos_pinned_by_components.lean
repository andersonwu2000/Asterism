import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- cos_pinned_by_components: solve 2×2 rotation linear system for cos via field algebra
-- p0*q0+p1*q1 = c*(p0²+p1²) after substituting the component equations; divide by nonzero norm.
theorem cos_pinned_by_components (c s p0 p1 q0 q1 : ℝ)
    (h0 : q0 = c * p0 - s * p1) (h1 : q1 = s * p0 + c * p1)
    (hp : ¬ (p0 = 0 ∧ p1 = 0)) :
    c = (p0 * q0 + p1 * q1) / (p0 ^ 2 + p1 ^ 2) := by
  have hne : p0 ^ 2 + p1 ^ 2 ≠ 0 := by
    intro h
    apply hp
    constructor
    · nlinarith [sq_nonneg p0, sq_nonneg p1]
    · nlinarith [sq_nonneg p0, sq_nonneg p1]
  rw [eq_div_iff hne, h0, h1]
  ring

end Problems.Geometry.banach_tarski

