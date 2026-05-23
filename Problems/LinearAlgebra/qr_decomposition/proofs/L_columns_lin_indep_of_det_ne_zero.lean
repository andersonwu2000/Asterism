import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs

namespace Problems.LinearAlgebra.qr_decomposition

-- columns_lin_indep_of_det_ne_zero: det ≠ 0 implies columns (A.transpose rows) are linearly
-- independent; proved via ker(mulVecLin) = ⊥ using A⁻¹*A=1, then mapping the standard basis.
-- entry_kind: Builder
theorem columns_lin_indep_of_det_ne_zero {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ) :
    A.det ≠ 0 → LinearIndependent ℝ A.transpose := by
  intro hdet
  have hker : LinearMap.ker A.mulVecLin = ⊥ := by
    rw [Matrix.ker_mulVecLin_eq_bot_iff]
    intro v hv
    have h1 : (A⁻¹ * A).mulVec v = v := by
      rw [Matrix.nonsing_inv_mul A (isUnit_iff_ne_zero.mpr hdet), Matrix.one_mulVec]
    rw [← h1, ← Matrix.mulVec_mulVec, hv, Matrix.mulVec_zero]
  have hbasis : LinearIndependent ℝ (fun i : Fin n => Pi.single i (1 : ℝ)) := by
    have h := (Pi.basisFun ℝ (Fin n)).linearIndependent
    convert h using 1
    ext i
    simp [Pi.basisFun_apply]
  have hkey : A.transpose = A.mulVecLin ∘ (fun i => Pi.single i 1) := by
    ext i j
    simp [Matrix.mulVec_single, Matrix.transpose_apply]
  rw [hkey]
  exact hbasis.map' A.mulVecLin hker

end Problems.LinearAlgebra.qr_decomposition