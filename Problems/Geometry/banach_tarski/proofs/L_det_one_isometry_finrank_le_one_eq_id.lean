-- Reduce the isometry/`= refl` packaging to one pure linear-algebra fact:
-- in finrank ≤ 1 every endomorphism `f` acts as `f x = (det f) • x`
-- (dim 0: both sides 0; dim 1: `f` is the scalar `det f`). Apply it to
-- `T`'s underlying linear map, plug `det = 1`, and `ext` closes `T = refl`.
-- The isometry structure is irrelevant to the core, hence dropped in the sub-goal.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11423

namespace Problems.Geometry.banach_tarski

def det_one_isometry_finrank_le_one_eq_id := @Problems.Geometry.banach_tarski.s11423

end Problems.Geometry.banach_tarski
