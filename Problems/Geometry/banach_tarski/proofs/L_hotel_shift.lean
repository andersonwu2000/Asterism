-- ρ''T = T∖D for the hotel T = ⋃ₙ ρⁿ''D: push ρ through the union (shift), then
-- peel the n=0 term using pairwise-disjoint orbits.
-- h_shift: image of union + ρ∘ρⁿ = ρⁿ⁺¹ collapses ρ''T to the shifted union ⋃ₙ ρⁿ⁺¹''D
--   (pure set algebra, no disjointness).
-- h_tail: the shifted union is exactly T with the n=0 piece D removed; ⊇ is trivial,
--   ⊆ uses hdisj (every ρⁿ⁺¹''D is disjoint from ρ⁰''D = D). Combine by rewriting.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11476

namespace Problems.Geometry.banach_tarski

def hotel_shift := @Problems.Geometry.banach_tarski.s11476

end Problems.Geometry.banach_tarski
