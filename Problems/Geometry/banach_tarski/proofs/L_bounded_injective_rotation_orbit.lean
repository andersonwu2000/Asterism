-- Absorb {0} via an off-origin isometry ρ whose 0-orbit stays in the ball and never
-- returns to 0.  Reduce the Set-level claim to a pointwise existence:
-- exists_bounded_injective_origin_orbit gives ρ with `(ρ^n) 0 ∈ ball` (⊆-part, after
-- `image_singleton` + `iUnion_subset`) and `(ρ^n) 0 ≠ 0` for n≥1 (the shift-disjointness
-- `Disjoint ((ρ^n)''{0}) {0}`), fed through the proved pairwise_disjoint_of_shift_disjoint
-- (s11430) to upgrade single shifts to the full ℕ-indexed Pairwise family.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11504

namespace Problems.Geometry.banach_tarski

def bounded_injective_rotation_orbit := @Problems.Geometry.banach_tarski.s11504

end Problems.Geometry.banach_tarski
