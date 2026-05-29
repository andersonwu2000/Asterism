import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem r0_components
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (t : ℝ) (x : E) :
    (R0 t x) 0 = Real.cos t * x 0 - Real.sin t * x 1 ∧
    (R0 t x) 1 = Real.sin t * x 0 + Real.cos t * x 1 := by aesop

end Problems.Geometry.banach_tarski
