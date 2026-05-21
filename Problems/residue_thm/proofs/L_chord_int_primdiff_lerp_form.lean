-- Convert the lerp form `(1-s)·z + s·w` to the offset form `z + s·(w-z)`
-- pointwise (pure `ring` after `push_cast`), then apply the offset-form FTC
-- specialization `chord_segment_form_primdiff` which packages the standard
-- chain-rule + `integral_eq_sub_of_hasDerivAt_of_le` argument for the convex
-- ball case (companion of the already-proved `segment_integral_eq_primitive_diff_in_ball`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10645

namespace Problems.residue_thm

def chord_int_primdiff_lerp_form := @Problems.residue_thm.s10645

end Problems.residue_thm
