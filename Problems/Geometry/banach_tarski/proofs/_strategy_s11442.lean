import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_orthogonal_matrix_isometry_equiv
import Problems.Geometry.banach_tarski.proofs.L_isometry_pow_realizes_matrix_pow
import Problems.Geometry.banach_tarski.proofs.L_z_rotation_block_orthogonal
import Problems.Geometry.banach_tarski.proofs.L_z_rotation_matrix_pow


namespace Problems.Geometry.banach_tarski

-- Construct the z-rotation isometry family by realizing each orthogonal block matrix.
-- `hreal`: each M θ is orthogonal (z_rotation_block_orthogonal) so PROVED
-- orthogonal_matrix_isometry_equiv gives an `e : E ≃ᵢ E` acting as `toEuclideanLin (M θ)`;
-- `choose` extracts the family R. Origin clause: linear maps fix 0 (`simp`). Realization
-- clause (3) is `hR` verbatim. Power law: IsometryEquiv `ext`, then
-- `isometry_pow_realizes_matrix_pow` reduces `(R θ)^n x` to `toEuclideanLin (M θ ^ n) x`,
-- and `z_rotation_matrix_pow` collapses `M θ ^ n = M (n·θ)`. Three sub-goals: the matrix
-- power law (pure matrix induction), the isometry-power/matrix-power bridge (group induction),
-- and per-θ orthogonality of the block (pure entry computation).
theorem s11442 :
    ∃ R : ℝ → (E ≃ᵢ E),
      (∀ θ : ℝ, R θ 0 = 0) ∧
      (∀ (θ : ℝ) (n : ℕ), (R θ) ^ n = R ((n : ℝ) * θ)) ∧
      (∀ (θ : ℝ) (x : E),
        R θ x =
          Matrix.toEuclideanLin
            (!![Real.cos θ, -Real.sin θ, 0;
                Real.sin θ,  Real.cos θ, 0;
                0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) x)  := by
  have hreal : ∀ θ : ℝ, ∃ e : E ≃ᵢ E, ∀ x : E,
      e x = Matrix.toEuclideanLin
        (!![Real.cos θ, -Real.sin θ, 0;
            Real.sin θ,  Real.cos θ, 0;
            0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) x :=
    fun θ => orthogonal_matrix_isometry_equiv _ (z_rotation_block_orthogonal θ)
  choose R hR using hreal
  refine ⟨R, fun θ => ?_, fun θ n => ?_, fun θ x => hR θ x⟩
  · rw [hR θ 0]; simp
  · ext x
    rw [isometry_pow_realizes_matrix_pow (R θ) _ (hR θ) n x, z_rotation_matrix_pow θ n,
        hR ((n : ℝ) * θ) x]

end Problems.Geometry.banach_tarski
