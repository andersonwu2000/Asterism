import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct proof: `Aᵀ A = 1 ⟹ ⟪Ax, Ay⟫ = ⟪x, y⟫`. Expand both Euclidean inners
-- componentwise (`PiLp.inner_apply`), reduce `toEuclideanLin A` to `A.mulVec`, and
-- rewrite the real scalar inner `⟪a,b⟫_ℝ = a*b` (`hr`). The remaining sum is the
-- dot-product identity `(A*ᵥx) ⬝ᵥ (A*ᵥy) = x ⬝ᵥ y` (`key`), closed by
-- `dotProduct_mulVec`/`mulVec_transpose`/`mulVec_mulVec` + `hA` + `one_mulVec`.
theorem s11391 {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) (hA : Matrix.transpose A * A = 1) :
    ∀ x y : EuclideanSpace ℝ (Fin n),
      inner ℝ (Matrix.toEuclideanLin A x) (Matrix.toEuclideanLin A y) = inner ℝ x y  := by
  intro x y
  have key : (A.mulVec x.ofLp) ⬝ᵥ (A.mulVec y.ofLp) = x.ofLp ⬝ᵥ y.ofLp := by
    rw [Matrix.dotProduct_mulVec, ← Matrix.mulVec_transpose, Matrix.mulVec_mulVec, hA,
      Matrix.one_mulVec]
  have hr : ∀ a b : ℝ, inner ℝ a b = a * b := by
    intro a b
    have h := RCLike.inner_apply (𝕜 := ℝ) a b
    simp only [starRingEnd_apply, star_trivial] at h
    exact h.trans (mul_comm b a)
  rw [PiLp.inner_apply, PiLp.inner_apply]
  simp only [Matrix.toEuclideanLin_apply, WithLp.ofLp_toLp, hr]
  exact key

end Problems.Geometry.banach_tarski
