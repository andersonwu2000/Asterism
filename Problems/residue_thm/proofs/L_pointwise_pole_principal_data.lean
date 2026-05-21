-- Per-pole Skolemisation: case-split on `a ∈ T`. For poles, get an isolating
-- ball via `isolating_radius_in_open_finset` (purely topological: U open + T
-- finite + a ∈ T), restrict `hf` to that punctured ball, then apply the
-- Cauchy-Laurent split via `principal_part_at_singularity_step_wrapper`
-- (a Builder wrapper around the proved toolkit
-- `principal_part_extraction_at_singularity`, isolated per LESSONS so the
-- framework's auto-import for `_strategy_*.lean` picks it up). For non-poles,
-- supply dummy witnesses; the hypothesis `a ∈ T` is vacuously false.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10467

namespace Problems.residue_thm

def pointwise_pole_principal_data := @Problems.residue_thm.s10467

end Problems.residue_thm
