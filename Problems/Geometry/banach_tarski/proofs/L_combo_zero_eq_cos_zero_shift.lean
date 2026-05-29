-- Amplitude-phase reduction: choose ψ with a = r·cosψ, b = r·sinψ (r = √(a²+b²) ≠ 0),
-- so cosφ·a − sinφ·b = r·cos(φ+ψ); its zero set is {cos(φ+ψ)=0} = (·−ψ)''{cosθ=0}.
--   amplitude_phase_exists  — the phase witness ψ (via Complex.arg of a+b·I);
--   combo_zero_set_eq       — the set equality given that phase data.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11450

namespace Problems.Geometry.banach_tarski

def combo_zero_eq_cos_zero_shift := @Problems.Geometry.banach_tarski.s11450

end Problems.Geometry.banach_tarski
