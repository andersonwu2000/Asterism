-- Mirror the proved non-origin-fixing absorption (s11458) but thread the origin-fixing
-- IsDecompOn data: (1) an origin-fixing Hilbert-hotel absorption equidecomp h : S² ≃ S²∖D
-- (rotation ρ and ρ⁻¹ fix 0, so both h and h.symm have origin-fixing decomp sets), then
-- (2) a generic transfer that carries a B-paradox with origin-fixing data to A preserving it.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11507

namespace Problems.Geometry.banach_tarski

def absorb_countable_paradoxical_origin_fixing := @Problems.Geometry.banach_tarski.s11507

end Problems.Geometry.banach_tarski
