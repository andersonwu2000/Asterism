import Mathlib
import Problems.pi1_circle.Defs

namespace Problems.pi1_circle

open Real

-- Forward rationale: Brick 1 from the Strategist brief — integer uniqueness
-- of the lifted endpoint reduces to cancellation by `2 * π ≠ 0` followed by
-- injectivity of the integer cast `ℤ → ℝ`. This is the missing piece that
-- lets the eventual `winding : Path (1 : Circle) 1 → ℤ` be defined
-- unambiguously on top of `lift_endpoint_mem_two_pi_int`.
-- entry_kind: Builder
theorem int_mul_two_pi_inj {m n : ℤ}
    (h : (m : ℝ) * (2 * π) = (n : ℝ) * (2 * π)) : m = n := by
  exact_mod_cast mul_right_cancel₀ Real.two_pi_pos.ne' h

end Problems.pi1_circle
