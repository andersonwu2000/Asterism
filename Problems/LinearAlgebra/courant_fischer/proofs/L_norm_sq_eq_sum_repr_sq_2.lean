import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- norm_sq_eq_sum_repr_sq_2: Parseval identity — ‖x‖² equals sum of squared
-- orthonormal-basis representation coefficients, via repr_apply_apply + sum_sq_inner_right.
theorem norm_sq_eq_sum_repr_sq_2
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 := by
  simp only [OrthonormalBasis.repr_apply_apply]
  exact ((hT.eigenvectorBasis hn).sum_sq_inner_right x).symm

end Problems.LinearAlgebra.courant_fischer
