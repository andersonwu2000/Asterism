import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_orthogonal_matrix_isometry_equiv
import Problems.Geometry.banach_tarski.proofs.L_x_rotation_block_orthogonal
import Problems.Geometry.banach_tarski.proofs.L_x_rotation_collision_countable

namespace Problems.Geometry.banach_tarski

-- Witness Q = rotation about the x-axis, realized from the orthogonal block
-- !![1,0,0; 0,cos φ,-sin φ; 0,sin φ,cos φ] via PROVED orthogonal_matrix_isometry_equiv.
-- Two sub-goals: (1) x_rotation_block_orthogonal — that block satisfies Mᵀ·M = 1
-- (Builder entry computation); (2) x_rotation_collision_countable — for the realized
-- family, every off-origin p has a countable z-axis-collision angle set (Backward:
-- (Q φ p) 0 = p 0 is φ-independent, so p 0 ≠ 0 ⟹ ∅; p 0 = 0 ⟹ (p 1,p 2) ≠ 0 and
-- cos φ·p 1 - sin φ·p 2 = 0 cuts a discrete set). `choose` extracts Q from the per-φ
-- realization; origin clause is `rw [hQ φ 0]; simp` (the realization is linear).
theorem s11447 :
    ∃ Q : ℝ → (E ≃ᵢ E),
      (∀ φ : ℝ, Q φ 0 = 0) ∧
      (∀ p : E, p ≠ 0 →
        {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}.Countable)  := by
  have hreal : ∀ φ : ℝ, ∃ e : E ≃ᵢ E, ∀ x : E,
      e x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x :=
    fun φ => orthogonal_matrix_isometry_equiv _ (x_rotation_block_orthogonal φ)
  choose Q hQ using hreal
  exact ⟨Q, fun φ => by rw [hQ φ 0]; simp, x_rotation_collision_countable Q hQ⟩

end Problems.Geometry.banach_tarski
