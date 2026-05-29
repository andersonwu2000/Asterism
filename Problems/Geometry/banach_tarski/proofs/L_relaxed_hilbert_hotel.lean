-- Relaxed Hilbert-hotel: same construction as the invariant version (s11467), but
-- T ⊆ A is supplied directly (hTA) instead of derived from ∀x∈A, ρx∈A — letting an
-- off-origin ρ (which maps closedBall 0 1 outside A) absorb D = {0}.
-- f = ρ on T = ⋃ₙ ρⁿ''D / id off T, inverse g = ρ⁻¹ on T / id off T; the 4
-- PartialEquiv laws + IsDecompOn are the proved abstract bricks, glued by Equidecomp.mk.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11505

namespace Problems.Geometry.banach_tarski

def relaxed_hilbert_hotel := @Problems.Geometry.banach_tarski.s11505

end Problems.Geometry.banach_tarski
