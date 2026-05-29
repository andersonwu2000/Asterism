import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct ℕ-induction bridging isometry-power to matrix-power (no sub-goals).
-- `induction n generalizing x`; base `simp` (e^0 = id, A^0 = 1). Step: `pow_succ`
-- on both sides, `change` exposes `(e^k * e) x` as `(e^k) (e x)` (defeq), rewrite
-- `he` then the IH, and `Matrix.toLpLin_apply`/`mulVec_mulVec` collapse
-- `toEuclideanLin (A^k) ∘ toEuclideanLin A = toEuclideanLin (A^k * A)`.
theorem s11444
    (e : E ≃ᵢ E) (A : Matrix (Fin 3) (Fin 3) ℝ)
    (he : ∀ x : E, e x = Matrix.toEuclideanLin A x) (n : ℕ) (x : E) :
    (e ^ n) x = Matrix.toEuclideanLin (A ^ n) x  := by
  induction n generalizing x with
  | zero => simp
  | succ k ih =>
    rw [pow_succ, pow_succ]
    change (e ^ k) (e x) = _
    rw [he, ih]
    simp only [Matrix.toLpLin_apply, Matrix.mulVec_mulVec]

end Problems.Geometry.banach_tarski
