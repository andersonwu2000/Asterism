import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_norm_sq_eq_sum_eigen
import Problems.LinearAlgebra.eckart_young.proofs.L_sum_eigen_lower_bound

namespace Problems.LinearAlgebra.eckart_young

-- Eckart–Young subspace lower bound: σ_k‖x‖ ≤ ‖Tx‖ on the top-(k+1) right-singular span.
-- Reduce to the squared form via the spectral diagonalization of T†T:
--  (1) `norm_sq_eq_sum_eigen`: ‖Tx‖² = ∑ λ_i ‖⟨b_i,x⟩‖²  (b,λ = eigbasis/eigvals of T†T)
--  (2) `sum_eigen_lower_bound`: σ_k²‖x‖² ≤ ∑ λ_i ‖⟨b_i,x⟩‖²  (subspace + descending eigvals)
-- Combine: σ_k²‖x‖² ≤ ‖Tx‖², rewrite as (σ_k‖x‖)² and take square roots.
theorem s11656 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  intro x hx
  have hid : ‖T x‖^2 = ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
      * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 :=
    norm_sq_eq_sum_eigen T x
  have hlb := sum_eigen_lower_bound T k hk x hx
  have hsq : (T.singularValues k)^2 * ‖x‖^2 ≤ ‖T x‖^2 := by rw [hid]; exact hlb
  have key : (T.singularValues k * ‖x‖)^2 ≤ ‖T x‖^2 := by rw [mul_pow]; exact hsq
  exact le_of_sq_le_sq key (norm_nonneg _)


end Problems.LinearAlgebra.eckart_young
