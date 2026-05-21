-- Pointwise: every `z ∈ Set.univ \ {z₀}` gets `DifferentiableAt ℂ P z`, then
-- `.differentiableWithinAt`. Two sub-goals isolate the local rewrite from the
-- analytic core:
--   `p_eventually_eq_cauchy_local` — pick `ε` (smaller than `dist z z₀` and `R`),
--     shrink a neighborhood of `z` to keep `ζ ≠ z₀` and `dist ζ z₀ > ε`, then
--     apply `hP` pointwise to get `P =ᶠ[𝓝 z]` the Cauchy-kernel function.
--   `cauchy_kernel_diff_at_outside` — `ζ ↦ ∮ w in C(z₀, ε), f w / (w - ζ)` is
--     differentiable at `z` whenever `ε < dist z z₀` (parametric Leibniz; the
--     integrand is differentiable in `ζ` for every `w` on the circle).
-- Combinator: `Filter.EventuallyEq.differentiableAt_iff` transfers
-- `DifferentiableAt` from kernel to `P`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10418

namespace Problems.residue_thm

def p_differentiable_on_punctured_plane := @Problems.residue_thm.s10418

end Problems.residue_thm
