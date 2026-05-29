import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem x_rot_fixes_first_coord
    (Q : ℝ → (E ≃ᵢ E))
    (hQ : ∀ (φ : ℝ) (x : E),
      Q φ x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) :
    ∀ (φ : ℝ), (Q φ p) 0 = p 0 := by aesop

end Problems.Geometry.banach_tarski
