import Mathlib.Analysis.InnerProductSpace.PiL2

/-!
# Orthogonal matrices preserve inner products

This file proves that orthogonal matrices (satisfying `Aᵀ A = 1`) act as isometries
on `EuclideanSpace ℝ (Fin n)`.

## Main statements

* `orthogonal_matrix_preserves_inner`: an orthogonal matrix preserves the real inner product
  on `EuclideanSpace ℝ (Fin n)`.
* `orthogonal_matrix_isometry_equiv`: an orthogonal matrix induces an isometry equivalence
  on `EuclideanSpace ℝ (Fin n)`.
-/

namespace Library.Geometry.BanachTarski.OrthogonalMatrices

/-- An orthogonal matrix $A$ (satisfying $Aᵀ A = 1$) preserves the real inner product on
`EuclideanSpace ℝ (Fin n)`. -/
theorem orthogonal_matrix_preserves_inner {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) (hA : Matrix.transpose A * A = 1) :
    ∀ x y : EuclideanSpace ℝ (Fin n),
      inner ℝ (Matrix.toEuclideanLin A x) (Matrix.toEuclideanLin A y) = inner ℝ x y := by
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
  simp only [Matrix.toLpLin_apply, WithLp.ofLp_toLp, hr]
  exact key

/-- An orthogonal matrix $A$ (satisfying $Aᵀ A = 1$) induces an isometry equivalence on
`EuclideanSpace ℝ (Fin n)`. -/
theorem orthogonal_matrix_isometry_equiv {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) (hA : Matrix.transpose A * A = 1) :
    ∃ e : EuclideanSpace ℝ (Fin n) ≃ᵢ EuclideanSpace ℝ (Fin n),
      ∀ x : EuclideanSpace ℝ (Fin n), e x = Matrix.toEuclideanLin A x := by
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

end Library.Geometry.BanachTarski.OrthogonalMatrices
