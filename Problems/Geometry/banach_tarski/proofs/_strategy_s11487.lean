import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_a_inv_left_inverse
import Problems.Geometry.banach_tarski.proofs.L_b_inv_left_inverse
import Problems.Geometry.banach_tarski.proofs.L_matrix_rep_monoid_hom
import Problems.Geometry.banach_tarski.proofs.L_orthogonal_to_linear_isometry_equiv

namespace Problems.Geometry.banach_tarski

-- Realize the two SO(3) generators through an abstract matrix-representation monoid hom.
--   • matrix_rep_monoid_hom: an injective, det-preserving `mat : (E ≃ₗᵢ E) →* Matrix` plus the
--     computation rule `hcomp` reading off the matrix of any isometry acting as `toEuclideanLin M`.
--   • orthogonal_to_linear_isometry_equiv: every orthogonal matrix is the action of some
--     `e : E ≃ₗᵢ[ℝ] E` (the `≃ₗᵢ` analogue of the proved `s11390`).
-- Orthogonality `Mᵀ * M = 1` of the two concrete generators is the cheap √2 computation, inlined.
-- Then g := ![eA, eB]; hcomp turns the actions into `mat (g i) = A/B`, and
-- a_inv_left_inverse/b_inv_left_inverse + `Matrix.inv_eq_left_inv` turn these into the inverse
-- literals. Each sub-goal is strictly simpler: an abstract reusable construction or a pure
-- matrix identity, with no entanglement between the hom and the generators.
theorem s11487 :
    ∃ (g : Fin 2 → (E ≃ₗᵢ[ℝ] E)) (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ),
      Function.Injective mat ∧
      (∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap)) ∧
      mat (g 0) = (1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] ∧
      (mat (g 0))⁻¹ = (1/3:ℝ) • !![1, 2*Real.sqrt 2, 0; -2*Real.sqrt 2, 1, 0; 0, 0, 3] ∧
      mat (g 1) = (1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1] ∧
      (mat (g 1))⁻¹ = (1/3:ℝ) • !![3, 0, 0; 0, 1, 2*Real.sqrt 2; 0, -2*Real.sqrt 2, 1]  := by
  have hoA : Matrix.transpose ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3])
      * ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3]) = 1 := by
    have h2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
    ext i j
    fin_cases i <;> fin_cases j <;>
      simp [Matrix.transpose, Matrix.mul_apply, Fin.sum_univ_three, Matrix.smul_apply] <;>
      nlinarith [h2]
  have hoB : Matrix.transpose ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1])
      * ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1]) = 1 := by
    have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
    ext i j
    fin_cases i <;> fin_cases j <;>
      simp [Matrix.transpose, Matrix.mul_apply, Fin.sum_univ_three, Matrix.smul_apply,
            Matrix.cons_val_zero, Matrix.cons_val_one] <;>
      ring_nf <;>
      nlinarith [hsq, sq_nonneg (Real.sqrt 2)]
  obtain ⟨mat, hinj, hdet, hcomp⟩ := matrix_rep_monoid_hom
  obtain ⟨eA, heA⟩ := orthogonal_to_linear_isometry_equiv _ hoA
  obtain ⟨eB, heB⟩ := orthogonal_to_linear_isometry_equiv _ hoB
  refine ⟨![eA, eB], mat, hinj, hdet, ?_, ?_, ?_, ?_⟩
  · change mat eA = _
    exact hcomp eA _ heA
  · change (mat eA)⁻¹ = _
    rw [hcomp eA _ heA]
    exact Matrix.inv_eq_left_inv (a_inv_left_inverse _ _ rfl rfl)
  · change mat eB = _
    exact hcomp eB _ heB
  · change (mat eB)⁻¹ = _
    rw [hcomp eB _ heB]
    exact Matrix.inv_eq_left_inv (b_inv_left_inverse _ _ rfl rfl)

end Problems.Geometry.banach_tarski
