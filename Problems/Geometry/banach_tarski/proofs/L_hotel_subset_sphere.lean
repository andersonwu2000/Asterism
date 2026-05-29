-- ρ^n applied to EuclideanSpace ℝ (Fin 3) blows past the default whnf budget; raise it.
-- hotel_subset_sphere: the orbit tower ⋃ₙ (ρ^n)''D of an origin-fixing isometry ρ stays
-- on S². Each (ρ^n) fixes 0 (induction, hfix) and an origin-fixing isometry preserves
-- norms (hnorm), so for d ∈ D ⊆ S² we get ‖(ρ^n) d‖ = ‖d‖ = 1. Sorry-free leaf.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11522

namespace Problems.Geometry.banach_tarski

def hotel_subset_sphere := @Problems.Geometry.banach_tarski.s11522

end Problems.Geometry.banach_tarski
