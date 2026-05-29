-- Hilbert-hotel absorption of the empty-word reps along the φ(of 1)⁻¹ tower.
-- ρ := φ(of 1)⁻¹; D := empty-word reps (head? = none); T := ⋃ₙ ρⁿ''D the orbit
-- tower; the piecewise map f (= ρ on T, id off T) bijects the source A onto A\D.
-- Concrete sub-goals: T ⊆ A (tower stays in source), orbits pairwise disjoint
-- (so hotel_shift gives ρ''T = T\D), and A\D = the b-block target.  The four
-- PartialEquiv laws + IsDecompOn come from the abstract proved Hilbert bricks.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11479

namespace Problems.Geometry.banach_tarski

def absorb_empty_word := @Problems.Geometry.banach_tarski.s11479

end Problems.Geometry.banach_tarski
