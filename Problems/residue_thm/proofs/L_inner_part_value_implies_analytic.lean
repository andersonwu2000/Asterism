-- Reduce `AnalyticOn ℂ P` on the punctured plane to `DifferentiableOn ℂ P`
-- via Cauchy's `DifferentiableOn.analyticOn` (on the open set `Set.univ \ {z₀}`).
-- The single sub-goal abstracts away the analytic↔differentiable bridge:
-- Builder only needs to derive complex differentiability of `P` at each `z ≠ z₀`
-- from the local integral formula in `hP`, no power-series manipulation.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10413

namespace Problems.residue_thm

def inner_part_value_implies_analytic := @Problems.residue_thm.s10413

end Problems.residue_thm
