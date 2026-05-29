-- Reuse the proved z-rotation isometry family (origin-fixing + power law + matrix realization);
-- the only new content is the off-axis collision-countability clause.
-- z_rotation_isometry_family_realizes_matrix supplies R0 with clauses (1),(2) and the matrix
-- realization `hreal`; feed `hreal` into the single sub-goal zrot_offaxis_collision_set_countable
-- (for an off-axis p, the rotated xy-component traces a circle, so {t | R0 t p = q} is countable).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11457

namespace Problems.Geometry.banach_tarski

def zrotation_offaxis_collision_family := @Problems.Geometry.banach_tarski.s11457

end Problems.Geometry.banach_tarski
