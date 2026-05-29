-- Absorb the single point {0} into closedBall by a Hilbert hotel run along an
-- off-origin rotation whose 0-orbit is injective and stays inside the ball.
-- (1) bounded_injective_rotation_orbit: existence of such ρ (orbit ⊆ ball + pairwise-disjoint).
-- (2) relaxed_hilbert_hotel: the `T ⊆ A` variant of the Hilbert-hotel equidecomposition,
--     dropping the too-strong `∀ x∈A, ρ x∈A` invariance (which fails for off-origin ρ since
--     ρ maps closedBall 0 1 to closedBall (ρ 0) 1).  Instantiate (2) at A = closedBall, D = {0}.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11501

namespace Problems.Geometry.banach_tarski

def ball_origin_absorb_equidecomp := @Problems.Geometry.banach_tarski.s11501

end Problems.Geometry.banach_tarski
