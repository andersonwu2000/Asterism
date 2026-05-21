-- Decompose into the dead-s10531 plan repaired with Q-continuity: build the C¹ loop
-- α · γ · β⁻¹ (closed since α 0 = β 0, α 1 = γ 0, β 1 = γ 1), apply h_loops, rearrange.
-- Sub-goal `c1_path_concat_integral_sum_cont` now takes `hQ_an` so its integral split
-- has IntervalIntegrable (the missing piece that made s10531's untyped concat unprovable
-- per its parent_needs_fix decline). `c1_path_reverse_integral_wrap` re-exposes the
-- already-proved `c1_path_reverse_integral` (Builder must inline since proved-sibling
-- citation is unavailable in patch.lean).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10657

namespace Problems.residue_thm

def path_diff_eq_connector := @Problems.residue_thm.s10657

end Problems.residue_thm
