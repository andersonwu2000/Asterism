-- Decompose analytic-glue into: (1) `f - ∑ P a` is analytic on `U \ T` directly,
-- (2) for each pole `a ∈ T`, a local analytic extension `g_a` exists on `Metric.ball a (R a)`
-- matching `f - ∑ P b` on the punctured ball (concretely `g_a = h a - ∑ b ∈ T.erase a, P b`),
-- and (3) a gluing lemma that, given (1)+(2), produces a global analytic `g` on `U` matching
-- `f - ∑ P a` on `U \ T`. Combinator: extract `g` from (3), then `f z = g z + ∑ P a z`
-- follows by ring from `g z = f z - ∑ P a z`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10459

namespace Problems.residue_thm

def analytic_glue_witness := @Problems.residue_thm.s10459

end Problems.residue_thm
