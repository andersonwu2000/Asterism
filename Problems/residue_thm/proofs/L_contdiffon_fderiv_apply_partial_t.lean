-- Direct: restrict hH to the open Ioo×Ioo via mono, drop one order with
-- `ContDiffOn.fderiv_of_isOpen`, then post-compose with the continuous-linear
-- evaluation map `ContinuousLinearMap.apply ℝ ℂ (0,1)` to land on the
-- fderiv-applied form. No further sub-goals needed (leaf-bypass).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10356

namespace Problems.residue_thm

def contdiffon_fderiv_apply_partial_t := @Problems.residue_thm.s10356

end Problems.residue_thm
