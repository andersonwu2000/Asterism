-- Reduce constancy of `H(s) = exp(-G(s))·(γ s - a)` (where `G(s) = ∫₀ˢ deriv γ /(γ-a)`)
-- to two prerequisites — H is differentiable on `[0,1]` and `derivWithin H [0,1] = 0` on
-- the interior `[0,1)` — and close via `constant_of_derivWithin_zero`. Evaluate at s=0
-- to identify H 0 = γ 0 - a (since the (0..0) integral vanishes), then multiply both
-- sides of `H(s) = γ 0 - a` by `exp(G(s))` and use `exp_add`+`exp_zero` to rearrange
-- to the target shape `exp(G(s))·(γ 0 - a) = γ s - a`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10302

namespace Problems.residue_thm

def exp_partial_path_int_mul_eq := @Problems.residue_thm.s10302

end Problems.residue_thm
