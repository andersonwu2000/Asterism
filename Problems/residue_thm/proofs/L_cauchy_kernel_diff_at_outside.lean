-- Reduce to differentiability of the bare circle-integral parameter map
-- `ζ ↦ ∮ w in C(z₀, ε), g w / (w - ζ)` at points `ζ` strictly outside the
-- circle. The `-((2πi)⁻¹ * _)` outer wrap is closed by `.const_mul.neg`.
--   `circle_int_param_diff_outside_at` — abstract sub-goal: parametric
--     Leibniz for a continuous integrand `g` on the sphere, evaluated at any
--     point at distance > r from the center.
-- Continuity of `f` on `sphere z₀ ε` is supplied inline from `hf.continuousOn`
-- restricted along `sphere z₀ ε ⊆ Metric.ball z₀ R \ {z₀}`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10437

namespace Problems.residue_thm

def cauchy_kernel_diff_at_outside := @Problems.residue_thm.s10437

end Problems.residue_thm
