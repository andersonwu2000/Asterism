-- Amplitude-phase: rewrite the level set through cos(φ+ψ), then transport by shift.
-- h1: cos φ·a − sin φ·b = √(a²+b²)·cos(φ+ψ) and √(a²+b²)≠0 collapse the LHS zero set
--     to {cos(φ+ψ)=0} (uses ha, hb, h);
-- h2: the pure shift identity {cos(φ+ψ)=0} = (·−ψ)''{cosθ=0} (no a,b dependence);
-- transitivity closes the parent — each sub-goal is a single, smaller set equality.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11452

namespace Problems.Geometry.banach_tarski

def combo_zero_set_eq := @Problems.Geometry.banach_tarski.s11452

end Problems.Geometry.banach_tarski
