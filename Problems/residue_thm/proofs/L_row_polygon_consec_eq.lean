-- Decompose row-strip homotopy invariance into per-cell Cauchy identities
-- on each ball B(c i j, r i j) and a telescoping sum over j.
-- (A) `cell_quad_chord_vert_diff`: on each cell (i,j), the chord-top minus
--     chord-bot equals V(i,j) − V(i,j+1) (Cauchy on the four corners of the
--     cell quadrilateral, all in Metric.ball (c i j) (r i j) ⊆ U).
-- Combinator: sum (A) over j ∈ range N. The RHS telescopes via
-- `Finset.sum_range_sub'` to V(i,0) − V(i,N). Both ends vanish: H τ 0 = γ 0
-- and H τ 1 = γ 0 force the integrand factor to be zero, and (N:ℝ)/N = 1
-- handles the upper boundary.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10639

namespace Problems.residue_thm

def row_polygon_consec_eq := @Problems.residue_thm.s10639

end Problems.residue_thm
