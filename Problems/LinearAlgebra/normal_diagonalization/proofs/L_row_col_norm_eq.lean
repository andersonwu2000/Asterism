import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs

namespace Problems.LinearAlgebra.normal_diagonalization

-- entry_kind: Builder
-- row_col_norm_eq: diagonal of Mᴴ*M and M*Mᴴ agree by normality, giving equal column/row 2-norms
theorem row_col_norm_eq {n : ℕ} (M : Matrix (Fin n) (Fin n) ℂ)
    (hcomm : Commute (Matrix.conjTranspose M) M) :
    ∀ i, ∑ k, ‖M k i‖ ^ 2 = ∑ k, ‖M i k‖ ^ 2 := by
  intro i
  have hdiag : (Matrix.conjTranspose M * M) i i = (M * Matrix.conjTranspose M) i i :=
    congr_fun (congr_fun hcomm i) i
  have star_mul_re : ∀ z : ℂ, (star z * z).re = ‖z‖ ^ 2 := fun z => by
    have h : star z * z = ↑(Complex.normSq z) := by
      rw [Complex.star_def]
      exact Complex.normSq_eq_conj_mul_self.symm
    rw [h, Complex.ofReal_re, Complex.normSq_eq_norm_sq]
  have mul_star_re : ∀ z : ℂ, (z * star z).re = ‖z‖ ^ 2 := fun z => by
    rw [mul_comm]; exact star_mul_re z
  have lhs_eq : ∑ k, ‖M k i‖ ^ 2 = ((Matrix.conjTranspose M * M) i i).re := by
    simp only [Matrix.mul_apply, Matrix.conjTranspose_apply, Complex.re_sum]
    congr 1; ext k
    exact (star_mul_re (M k i)).symm
  have rhs_eq : ∑ k, ‖M i k‖ ^ 2 = ((M * Matrix.conjTranspose M) i i).re := by
    simp only [Matrix.mul_apply, Matrix.conjTranspose_apply, Complex.re_sum]
    congr 1; ext k
    exact (mul_star_re (M i k)).symm
  rw [lhs_eq, rhs_eq, hdiag]

end Problems.LinearAlgebra.normal_diagonalization