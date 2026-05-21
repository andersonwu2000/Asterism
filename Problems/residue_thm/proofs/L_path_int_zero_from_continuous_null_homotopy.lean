-- Discretize the continuous null-homotopy via a Lebesgue grid:
-- (1) `homotopy_lebesgue_grid` extracts N and per-cell balls in U covering H on each cell;
-- (2) `path_int_zero_given_homotopy_grid` runs the cell-boundary telescoping argument
--     (each cell-boundary PL loop lies in a ball, hence integrates to 0 by Cauchy on a ball;
--     the cell sum telescopes to the outer boundary, whose only nontrivial side is γ; the
--     constant sides give 0 via `hHleft`, `hHright`, `hH1`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10570

namespace Problems.residue_thm

def path_int_zero_from_continuous_null_homotopy := @Problems.residue_thm.s10570

end Problems.residue_thm
