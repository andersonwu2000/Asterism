-- Fubini swap on the (t, θ)-double interval integral for the Q-kernel: reduce both
-- interval integrals to set integrals over `Set.Ioc`, apply `integral_integral_swap`
-- on the product measure, and refold back. Only non-trivial premise is joint
-- integrability of the rational integrand on the compact product `Ioc 0 1 × Ioc 0 (2π)`.
--   (1) `q_kernel_integrand_integrable` — joint integrability of
--       `(t, θ) ↦ deriv γ t * (deriv (circleMap a ε) θ •
--                              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))`
--       on the product of restricted Lebesgue measures.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10567

namespace Problems.residue_thm

def q_kernel_double_fubini_swap := @Problems.residue_thm.s10567

end Problems.residue_thm
