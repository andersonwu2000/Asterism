-- Glue the piecewise velocity via `ContinuousOn.if`:
-- (1) continuity of the left branch `s ↦ 2·derivWithin α' (Icc 0 1) (2s)` on `Icc 0 (1/2)`,
-- (2) continuity of the right branch `s ↦ 2·derivWithin β' (Icc 0 1) (2s-1)` on `Icc (1/2) 1`,
-- (3) junction agreement at s = 1/2 follows inline from `hα'_deriv` and `hβ'_deriv`
--     (both branches evaluate to 0 there).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10667

namespace Problems.residue_thm

def piecewise_velocity_continuous_on_icc := @Problems.residue_thm.s10667

end Problems.residue_thm
