import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_orthogonal_matrix_preserves_inner

namespace Problems.Geometry.banach_tarski

-- Decompose: orthogonal A → IsometryEquiv via a LinearIsometryEquiv, then `.toIsometryEquiv`.
-- One sub-goal: `orthogonal_matrix_preserves_inner` — `toEuclideanLin A` preserves the real inner
-- product (the orthogonality content: ⟪Ax,Ay⟫ = ⟪x,AᵀAy⟫ = ⟪x,y⟫). The rest is pure structural
-- packaging on top: `LinearMap.isometryOfInner` turns the inner-preservation into a `LinearIsometry`
-- f; f is injective hence (finite dim) surjective via `LinearMap.injective_iff_surjective`;
-- `LinearIsometryEquiv.ofSurjective` upgrades f to a `≃ₗᵢ`; `.toIsometryEquiv` is the witness, and
-- its action is defeq to `toEuclideanLin A` (rfl). The sub-goal is strictly simpler: a pure
-- inner-product/matrix identity, no existential or isometry packaging.
theorem s11390 {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) (hA : Matrix.transpose A * A = 1) :
    ∃ e : EuclideanSpace ℝ (Fin n) ≃ᵢ EuclideanSpace ℝ (Fin n),
      ∀ x : EuclideanSpace ℝ (Fin n), e x = Matrix.toEuclideanLin A x  := by
  have h_inner := orthogonal_matrix_preserves_inner A hA
  let f : EuclideanSpace ℝ (Fin n) →ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n) :=
    (Matrix.toEuclideanLin A).isometryOfInner h_inner
  have hinj : Function.Injective f := f.injective
  have hsurj : Function.Surjective f := by
    have h := (LinearMap.injective_iff_surjective (f := f.toLinearMap))
    exact h.mp hinj
  let L := LinearIsometryEquiv.ofSurjective f hsurj
  refine ⟨L.toIsometryEquiv, ?_⟩
  intro x
  rfl

end Problems.Geometry.banach_tarski
