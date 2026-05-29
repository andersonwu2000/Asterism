import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_orthogonal_matrix_preserves_inner

namespace Problems.Geometry.banach_tarski

-- orthogonal_to_linear_isometry_equiv: promote orthogonal M to LinearIsometryEquiv via
-- inner-product preservation → norm preservation → LinearIsometry → surjectivity (fin-dim).
-- entry_kind: Backward
theorem orthogonal_to_linear_isometry_equiv
    (M : Matrix (Fin 3) (Fin 3) ℝ) (hM : Matrix.transpose M * M = 1) :
    ∃ e : E ≃ₗᵢ[ℝ] E, ∀ x : E, e x = Matrix.toEuclideanLin M x := by
  have h_inner : ∀ x y : E,
      inner ℝ (Matrix.toEuclideanLin M x) (Matrix.toEuclideanLin M y) = inner ℝ x y :=
    orthogonal_matrix_preserves_inner M hM
  have hnorm : ∀ x : E, ‖Matrix.toEuclideanLin M x‖ = ‖x‖ := by
    intro x
    have := h_inner x x
    simp only [real_inner_self_eq_norm_sq] at this
    nlinarith [norm_nonneg (Matrix.toEuclideanLin M x), norm_nonneg x]
  let f : E →ₗᵢ[ℝ] E := ⟨Matrix.toEuclideanLin M, hnorm⟩
  have hinj : Function.Injective f.toLinearMap := f.injective
  have hsurj : Function.Surjective f.toLinearMap := by
    apply (f.toLinearMap.injective_iff_surjective_of_finrank_eq_finrank _).mp hinj
    rfl
  exact ⟨LinearIsometryEquiv.ofSurjective f hsurj, fun x => rfl⟩

end Problems.Geometry.banach_tarski
