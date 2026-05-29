-- Absorb the countable fixed-point set D back into the sphere to upgrade a paradox of S²∖D.
-- (1) sphere_hilbert_hotel_absorb: a Hilbert-hotel rotation makes S² equidecomposable with S²∖D
--     (uses 0∉D and countability of D; an Equidecomp h with source S², target S²∖D).
-- (2) paradoxical_transfer_along_equidecomp: a paradox transfers along equidecomposability —
--     if A ≃ B and B is paradoxical then A is paradoxical (fully abstract over sets, no spheres).
-- Combinator: get h from (1), feed it with the given hp (paradox of S²∖D) into (2). Each sub-goal
-- is strictly simpler — (1) drops the paradox layer, (2) drops all geometry/free-group machinery.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11458

namespace Problems.Geometry.banach_tarski

def absorb_countable_paradoxical := @Problems.Geometry.banach_tarski.s11458

end Problems.Geometry.banach_tarski
