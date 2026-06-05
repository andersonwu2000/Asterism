import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- norm_sq_eq_sum_repr_sq: Parseval identity — ‖x‖² equals sum of squared eigenbasis
-- repr coefficients, via the isometry OrthonormalBasis.repr and PiLp.norm_sq_eq_of_L2.
theorem norm_sq_eq_sum_repr_sq
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 := by
  have hnorm : ‖(hT.eigenvectorBasis hn).repr x‖ = ‖x‖ :=
    LinearIsometryEquiv.norm_map _ x
  rw [← hnorm]
  rw [PiLp.norm_sq_eq_of_L2]
  congr 1; ext i
  exact Real.norm_eq_abs _ ▸ sq_abs _


end Problems.LinearAlgebra.courant_fischer
