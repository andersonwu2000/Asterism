-- Decomposition: first produce per-pole outer radii r — positivity and
-- AnalyticOn on the punctured disk — from openness of U and discreteness of T
-- inside U; then shrink to inner radii ρ ∈ (0, r) simultaneously disjoint from
-- γ's compact image and pairwise disjoint between distinct poles.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10321

namespace Problems.residue_thm

def exists_isolating_radii_for_finset_poles := @Problems.residue_thm.s10321

end Problems.residue_thm
