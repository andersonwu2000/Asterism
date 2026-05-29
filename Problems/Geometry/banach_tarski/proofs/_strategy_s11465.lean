import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_cos_pinned_by_components
import Problems.Geometry.banach_tarski.proofs.L_r0_components

namespace Problems.Geometry.banach_tarski

-- collision set {t | R0 t p = q} ⊆ cosine level set, via the 2×2 z-rotation system.
-- Two strictly simpler sub-goals: (1) `r0_components` unfolds the matrix action into
-- its first-two scalar component equations q₀ = c·p₀ - s·p₁, q₁ = s·p₀ + c·p₁ (matrix
-- algebra, no analysis); (2) `cos_pinned_by_components` solves that 2×2 linear system
-- for cos t = (p₀q₀+p₁q₁)/(p₀²+p₁²) given off-axis ¬(p₀=0∧p₁=0) (pure field algebra).
-- After `intro t ht` and rewriting ht : R0 t p = q into the components, `exact` combines.
theorem s11465
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) (hp : ¬ (p 0 = 0 ∧ p 1 = 0)) (q : E) :
    {t : ℝ | R0 t p = q} ⊆
      {t : ℝ | Real.cos t = (p 0 * q 0 + p 1 * q 1) / (p 0 ^ 2 + p 1 ^ 2)}  := by
  intro t ht
  simp only [Set.mem_setOf_eq] at ht ⊢
  obtain ⟨hc0, hc1⟩ := r0_components R0 hreal t p
  rw [ht] at hc0 hc1
  exact cos_pinned_by_components (Real.cos t) (Real.sin t) (p 0) (p 1) (q 0) (q 1) hc0 hc1 hp

end Problems.Geometry.banach_tarski
