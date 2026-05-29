import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_freegroup_paradoxical

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem z_rotation_matrix_orthogonal (θ : ℝ) :
    Matrix.transpose
        (!![Real.cos θ, -Real.sin θ, 0;
            Real.sin θ,  Real.cos θ, 0;
            0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) *
      (!![Real.cos θ, -Real.sin θ, 0;
          Real.sin θ,  Real.cos θ, 0;
          0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) = 1 := by apply freegroup_paradoxical <;> assumption

end Problems.Geometry.banach_tarski
