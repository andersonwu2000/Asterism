-- Thread monotonicity through the change-of-variables step: pick a smooth, monotone
-- Hermite reparametrization φ of [0,1] (existence with `0 ≤ deriv φ`), transfer the
-- non-integral C¹/endpoint/flat-derivWithin/avoid properties through the composition,
-- and close the integral identity via the monotone-φ variant of change-of-variables.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10579

namespace Problems.residue_thm

def c1_path_smooth_reparam_flat_endpoints := @Problems.residue_thm.s10579

end Problems.residue_thm
