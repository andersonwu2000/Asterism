-- Hilbert-hotel absorption of the countable set D back into the sphere.
-- Pick a rotation ρ fixing 0 whose orbits ρⁿ''D are pairwise disjoint (cite the
-- proved sibling exists_rotation_pairwise_disjoint_orbit_off_origin); ρ fixes 0,
-- so it maps S² into itself (isometry_fixing_origin_maps_sphere); then the abstract
-- builder equidecomp_hilbert_hotel sends D̃ = ⋃ₙ ρⁿ''D to D̃∖D and fixes the rest,
-- yielding an Equidecomp with source S², target S²∖D. Each sub-goal is strictly
-- simpler: one is a one-line isometry fact, the other a geometry-free, free-group-free,
-- countability-free PartialEquiv/IsDecompOn construction over abstract sets A,D.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11462

namespace Problems.Geometry.banach_tarski

def sphere_hilbert_hotel_absorb := @Problems.Geometry.banach_tarski.s11462

end Problems.Geometry.banach_tarski
