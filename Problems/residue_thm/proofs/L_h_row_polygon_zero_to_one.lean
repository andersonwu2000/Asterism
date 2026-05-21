-- Decompose row-polygon homotopy invariance (τ=0 vs τ=1) into
-- (A) a single-step row equality `row_polygon_consec_eq` covering one strip τ ∈ [i/N, (i+1)/N]
-- (Cauchy on each cell ball plus telescoping over j), and (B) `row_polygon_telescope` which
-- iterates the step from i=0 to i=N to bridge τ=0 with τ=N/N=1.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10630

namespace Problems.residue_thm

def h_row_polygon_zero_to_one := @Problems.residue_thm.s10630

end Problems.residue_thm
