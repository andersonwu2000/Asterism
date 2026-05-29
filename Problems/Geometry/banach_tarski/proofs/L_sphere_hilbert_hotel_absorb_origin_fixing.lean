-- Origin-fixing Hilbert-hotel absorption S² ≃ S²∖D, exposing origin-fixing decomp data.
-- Pick a rotation ρ fixing 0 with pairwise-disjoint orbits ρⁿ''D (proved sibling
-- exists_rotation_pairwise_disjoint_orbit_off_origin); build the piecewise hotel map
-- f = ρ on T = ⋃ₙ ρⁿ''D / id off T, g = ρ.symm on T / id off T, and assemble the
-- Equidecomp from the proved abstract bricks map_source/target_hilbert + left/right_inv_hilbert
-- (4 PartialEquiv laws) with hotel_shift (ρ''T = T∖D). Two strictly-simpler NEW sub-goals:
--   • hotel_subset_sphere — the orbit tower T stays on S² (ρⁿ fix 0, isometry preserves sphere);
--   • is_decomp_hilbert_origin_fixing — IsDecompOn with witness set {ρ,1} ALL FIXING 0, the
--     origin-fixing strengthening of the proved is_decomp_hilbert; reused for both h (via ρ)
--     and h.symm (via ρ.symm, which fixes 0 too).  Both sub-goals drop the equidecomp layer.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11511

namespace Problems.Geometry.banach_tarski

def sphere_hilbert_hotel_absorb_origin_fixing := @Problems.Geometry.banach_tarski.s11511

end Problems.Geometry.banach_tarski
