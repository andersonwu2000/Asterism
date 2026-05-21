-- Decomposition: build ρ from (a) per-pole positivity of infDist to γ's compact
-- image (analytic content: compactness + γ avoiding T) and (b) a uniform positive
-- lower bound on pairwise distances inside T (pure Finset combinatorics).
-- Set ρ a := min (r a / 2) (min (infDist a (γ '' [0,1]) / 2) (d / 4)). Each of
-- the four conjuncts (positivity, < r, γ-disjointness via
-- disjoint_closedBall_of_lt_infDist, pairwise via closedBall_disjoint_closedBall)
-- follows from ρ a ≤ the corresponding ingredient.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10322

namespace Problems.residue_thm

def exists_inner_radii_disjoint := @Problems.residue_thm.s10322

end Problems.residue_thm
