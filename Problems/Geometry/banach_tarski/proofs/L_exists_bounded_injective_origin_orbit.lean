-- Absorb {0} via an off-origin rotation: ρ conjugates a linear rotation R by a
-- translation that moves the rotation axis off the origin, so the 0-orbit traces a
-- circle of radius ‖c‖ ≤ 1/2 through the origin.
-- (1) exists_small_irrational_rotation: a linear rotation R and a small vector c
--     (‖c‖ ≤ 1/2) such that no positive power of R fixes c (irrational angle).
-- (2) conjugate_origin_orbit: build ρ x = R(x - c) + c; then (ρ^n) 0 = c - R^n c,
--     so ‖(ρ^n) 0‖ ≤ ‖c‖ + ‖R^n c‖ = 2‖c‖ ≤ 1 (in the ball) and (ρ^n) 0 = 0 ↔
--     R^n c = c, excluded for n ≥ 1 by hfix.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11509

namespace Problems.Geometry.banach_tarski

def exists_bounded_injective_origin_orbit := @Problems.Geometry.banach_tarski.s11509

end Problems.Geometry.banach_tarski
