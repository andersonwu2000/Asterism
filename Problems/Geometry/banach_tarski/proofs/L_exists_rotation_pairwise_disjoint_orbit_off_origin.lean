-- Hilbert-hotel disjoint-orbit existence (off-origin), THIN glue over proved bricks.
-- Two sub-goals: (1) zrotation_offaxis_collision_family — a z-rotation isometry family
-- R₀ fixing 0, with the power law, and countable collision-angle sets for every off-axis
-- point; (2) conj_pairwise_transport — transport a pairwise-disjoint orbit through the
-- single conjugation g⁻¹·ρ₀·g.  All the axis-selection and assembly is inline:
--   • get an origin-fixing isometry g moving every p ∈ D off the z-axis, by feeding
--     good_angle_avoids_zaxis the x-rotation family Q (zaxis_collision_angles_per_point_countable);
--     the p ≠ 0 side-condition comes from hD0 (this is where 0 ∉ D is load-bearing);
--   • R₀'s off-axis collision clause then holds on g '' D, so good_angle_avoids_collisions
--     yields a z-rotation ρ₀ with shift-disjoint orbit over g '' D, upgraded to Pairwise by
--     pairwise_disjoint_of_shift_disjoint;
--   • conjugating by g (conj_pairwise_transport) carries Pairwise back to ρ := g⁻¹·ρ₀·g over D,
--     and ρ 0 = 0 since g, ρ₀ both fix 0.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11454

namespace Problems.Geometry.banach_tarski

def exists_rotation_pairwise_disjoint_orbit_off_origin := @Problems.Geometry.banach_tarski.s11454

end Problems.Geometry.banach_tarski
