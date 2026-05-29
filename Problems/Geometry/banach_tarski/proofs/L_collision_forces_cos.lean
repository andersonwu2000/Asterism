-- collision set {t | R0 t p = q} ⊆ cosine level set, via the 2×2 z-rotation system.
-- Two strictly simpler sub-goals: (1) `r0_components` unfolds the matrix action into
-- its first-two scalar component equations q₀ = c·p₀ - s·p₁, q₁ = s·p₀ + c·p₁ (matrix
-- algebra, no analysis); (2) `cos_pinned_by_components` solves that 2×2 linear system
-- for cos t = (p₀q₀+p₁q₁)/(p₀²+p₁²) given off-axis ¬(p₀=0∧p₁=0) (pure field algebra).
-- After `intro t ht` and rewriting ht : R0 t p = q into the components, `exact` combines.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11465

namespace Problems.Geometry.banach_tarski

def collision_forces_cos := @Problems.Geometry.banach_tarski.s11465

end Problems.Geometry.banach_tarski
