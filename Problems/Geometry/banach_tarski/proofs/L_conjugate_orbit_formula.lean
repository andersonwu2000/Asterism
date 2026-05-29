-- Closed form for the origin-orbit of the conjugated rotation ρ x = R(x-c)+c.
-- Induction on n: base 0 is `c - c = 0`; the step rewrites ρ^(k+1) = ρ ∘ ρ^k,
-- applies the inductive hypothesis and the defining equation hρ, uses linearity
-- of R (map_sub) and R^(k+1) = R ∘ R^k, then closes by abelian-group algebra.
-- the (ρ^n : E ≃ᵢ E) application on EuclideanSpace ℝ (Fin 3) blows past the
-- default 200k heartbeat whnf limit; lift it.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11517

namespace Problems.Geometry.banach_tarski

def conjugate_orbit_formula := @Problems.Geometry.banach_tarski.s11517

end Problems.Geometry.banach_tarski
