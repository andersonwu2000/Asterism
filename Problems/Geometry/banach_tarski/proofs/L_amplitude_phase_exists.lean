-- Amplitude-phase witness via the complex argument: take ψ = arg ⟨a,b⟩.
-- Then cos ψ = re/‖z‖ = a/√(a²+b²) and sin ψ = im/‖z‖ = b/√(a²+b²); since
-- a≠0∨b≠0 gives ‖z‖=√(a²+b²)≠0, multiplying back cancels. Direct, no sub-goals.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11451

namespace Problems.Geometry.banach_tarski

def amplitude_phase_exists := @Problems.Geometry.banach_tarski.s11451

end Problems.Geometry.banach_tarski
