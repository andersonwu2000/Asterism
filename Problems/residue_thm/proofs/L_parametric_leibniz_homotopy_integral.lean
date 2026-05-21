-- Apply Mathlib's parametric interval-integral Leibniz at τ ∈ Ioo 0 1
-- (where Ioo 0 1 ∈ 𝓝 τ unlocks the lemma). Sub-goals provide: integrand
-- IntervalIntegrable on [0,1] (1), τ-partial AEStronglyMeasurable (2), uniform
-- L∞ bound on the τ-partial over Ioo 0 1 (3), and pointwise HasDerivAt of the
-- integrand in τ for a.e. t over Ioo 0 1 (4). Combinator:
-- intervalIntegral.hasDerivAt_integral_of_dominated_loc_of_deriv_le with
-- s := Ioo 0 1 and bound := const M.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10334

namespace Problems.residue_thm

def parametric_leibniz_homotopy_integral := @Problems.residue_thm.s10334

end Problems.residue_thm
