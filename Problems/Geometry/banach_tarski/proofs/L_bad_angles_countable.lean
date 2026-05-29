-- Bad-angle set = ⋃ over n the per-n fiber; split the union over ℕ (Countable).
-- For n=0 the fiber is empty (1 ≤ n fails); for n ≥ 1 it is the D×D-biUnion of
-- the scaled collision sets {θ | R(nθ)p=q}, each countable by sub-goal
-- [scaled_collision_countable] (preimage of hcol's set under θ ↦ nθ, n ≠ 0).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11434

namespace Problems.Geometry.banach_tarski

def bad_angles_countable := @Problems.Geometry.banach_tarski.s11434

end Problems.Geometry.banach_tarski
