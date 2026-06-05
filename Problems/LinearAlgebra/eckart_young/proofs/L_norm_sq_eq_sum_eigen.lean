import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- norm_sq_eq_sum_eigen: ‖Tx‖² = ∑ λᵢ‖⟨bᵢ,x⟩‖² where (b,λ) = eigenbasis/eigvals of T†T.
-- Reduce ‖Tx‖² = re⟪T†T x,x⟫ via norm_sq_eq_re_inner + adjoint_inner_left,
-- then expand with sum_inner_mul_inner and collapse each term via hA-symmetry + conj_mul.
theorem norm_sq_eq_sum_eigen {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (x : E) :
    ‖T x‖^2 = ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
      * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 := by
  set hA := T.isSymmetric_adjoint_comp_self
  rw [norm_sq_eq_re_inner (𝕜 := 𝕜), ← LinearMap.adjoint_inner_left]
  simp only [← LinearMap.comp_apply]
  classical
  rw [← OrthonormalBasis.sum_inner_mul_inner (hA.eigenvectorBasis rfl) ((T.adjoint ∘ₗ T) x) x,
      map_sum]
  apply Finset.sum_congr rfl
  intro i _
  rw [hA x (hA.eigenvectorBasis rfl i), hA.apply_eigenvectorBasis rfl i, inner_smul_right,
      ← inner_conj_symm, mul_assoc, RCLike.conj_mul,
      ← RCLike.ofReal_pow, ← RCLike.ofReal_mul, RCLike.ofReal_re]

end Problems.LinearAlgebra.eckart_young

