-- Reduce `exp(∫ deriv γ /(γ-a)) = 1` to constancy of `s ↦ exp(G(s))·(γ 0-a)`
-- where `G(s) = ∫₀ˢ deriv γ /(γ-a)`. The sub-goal `exp_partial_path_int_mul_eq`
-- packages the constancy as `exp(G(s))·(γ 0-a) = γ s - a` on [0,1]; specialise
-- to s=1, rewrite γ 1 ↦ γ 0 via `hclosed`, cancel `γ 0 - a ≠ 0` (from `havoid 0`)
-- with `mul_left_eq_self₀` to extract `exp(G(1)) = 1`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10301

namespace Problems.residue_thm

def exp_path_integral_eq_one := @Problems.residue_thm.s10301

end Problems.residue_thm
