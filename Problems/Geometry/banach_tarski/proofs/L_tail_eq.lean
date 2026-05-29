-- ρ''T = T∖D via direct set-extensionality (no decomposition needed; leaf-bypass).
-- LHS = ⋃ₙ ρⁿ⁺¹''D = the union missing its n=0 term. After `ext`/`simp [mem_iUnion,mem_diff]`:
--   ⊇ (backward): x∈ρⁿ''D∧x∉D ⇒ n≠0 (else x∈ρ⁰''D=D, contra hxD) ⇒ x∈ρ^(m+1)''D.
--   ⊆ (forward):  x∈ρⁿ⁺¹''D ⇒ trivially in the full union; x∉D since x∈ρ⁰''D=D would
--                 collide with x∈ρⁿ⁺¹''D under hdisj (0≠n+1).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11484

namespace Problems.Geometry.banach_tarski

def tail_eq := @Problems.Geometry.banach_tarski.s11484

end Problems.Geometry.banach_tarski
