import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_orthogonal_matrix_a
import Problems.Geometry.banach_tarski.proofs.L_orthogonal_matrix_b

namespace Problems.Geometry.banach_tarski

-- Split the orthogonality conjunction into the two independent matrix computations.
-- h_a / h_b each verify Mᵀ * M = 1 for one concrete generator (pure √2 arithmetic),
-- strictly simpler than the parent since only one matrix is in scope per sub-goal.
theorem s11389
    (A B : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1/3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hB : B = (1/3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1]) :
    Matrix.transpose A * A = 1 ∧ Matrix.transpose B * B = 1  := by
  have h_a : Matrix.transpose A * A = 1 := orthogonal_matrix_a A hA
  have h_b : Matrix.transpose B * B = 1 := orthogonal_matrix_b B hB
  exact ⟨h_a, h_b⟩

end Problems.Geometry.banach_tarski
