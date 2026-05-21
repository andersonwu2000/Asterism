-- Direct: `windingNumber γ a` is defined as `Classical.choose h` under the same
-- existence hypothesis. `unfold` + `dif_pos h` + `Classical.choose_spec h` closes the goal.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10274

namespace Problems.residue_thm

def winding_number_integral_of_exists := @Problems.residue_thm.s10274

end Problems.residue_thm
