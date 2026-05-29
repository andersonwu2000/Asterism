-- x-rotation fixes coord 0 (=p 0) and sends coord 1 to cos φ·p₁ − sin φ·p₂; reduce the
-- two-clause collision set to the second-coord zero set, then case-split on p 0.
-- Sub-goals: x_rot_fixes_first_coord, x_rot_second_coord (component formulas, Builder);
-- cos_sin_combo_zero_countable (zeros of a nonzero cos/sin combination are countable, Backward).
-- p 0 ≠ 0 ⟹ clause-0 fails ⟹ ∅; p 0 = 0 ⟹ (p₁,p₂)≠0 (from p≠0) ⟹ trig zero set, .mono.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11448

namespace Problems.Geometry.banach_tarski

def x_rotation_collision_countable := @Problems.Geometry.banach_tarski.s11448

end Problems.Geometry.banach_tarski
