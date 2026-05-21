-- Split `exp(-G(s))` as `exp ∘ (-) ∘ G` where `G(s) := ∫₀ˢ deriv γ /(γ-a)`.
-- Sub-goal: differentiability of `G` (FTC + continuity of the integrand);
-- closer: `.neg` then `DifferentiableOn.cexp` since `Complex.exp` is entire.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10305

namespace Problems.residue_thm

def differentiable_exp_neg_integral := @Problems.residue_thm.s10305

end Problems.residue_thm
