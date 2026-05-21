-- (1) `q_eq_inner_cauchy_principal_part` applies `principal_part_extraction_at_singularity`
--     to the lone pole `a`, yielding a principal part `P` analytic on `ℂ\{a}` with
--     decay at ∞ and an inner-Cauchy-integral representation. Liouville on the entire
--     extension of `Q - P` (regular remainder vanishes at ∞) collapses to `Q = P`
--     globally on `ℂ\{a}`.
-- (2) `inner_cauchy_part_path_int_zero_residue_zero` integrates the Cauchy-integral
--     form of `P` along `γ`: Fubini-swap with the inner circle, the inner
--     `∫₀¹ γ'(t)/(w-γ t) dt` factors through `windingNumber γ w` which is constant on
--     `ball a ε` (γ stays away from a), reducing to `windingNumber γ a · ∮_C(a,ε) Q`;
--     `circle_int_eq_two_pi_residue` evaluates the circle integral to
--     `2πi · residue Q a`, which is `0` by `hQ_res`.
-- Conclude `∫_γ Q = ∫_γ P = 0` via `intervalIntegral.integral_congr`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10501

namespace Problems.residue_thm

def analytic_residue_zero_decay_closed_loop_zero := @Problems.residue_thm.s10501

end Problems.residue_thm
