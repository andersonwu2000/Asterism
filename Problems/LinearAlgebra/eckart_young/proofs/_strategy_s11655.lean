import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_re_inner_symm_eq_sum_eigenvalues_2
import Problems.LinearAlgebra.eckart_young.proofs.L_termwise_eigenvalue_bound

namespace Problems.LinearAlgebra.eckart_young

-- Spectral lower bound on the top-(k+1) right-singular span: reduce `σ_k‖x‖ ≤ ‖T x‖`
-- to its square `σ_k²‖x‖² ≤ ‖T x‖²` (via `le_of_sq_le_sq`), then diagonalize the Gram
-- operator `T†∘T` in its eigenbasis. Two sub-goals:
--   `re_inner_symm_eq_sum_eigenvalues_2` — the Rayleigh identity
--     `re⟪Sx,x⟫ = ∑ λ_i ‖⟪b_i,x⟫‖²` for a symmetric `S` (here `S = T†∘T`);
--   `termwise_eigenvalue_bound` — per-coordinate `σ_k²‖⟪b_i,x⟫‖² ≤ λ_i‖⟪b_i,x⟫‖²`
--     (antitone eigenvalues for `i ≤ k`, orthogonality `⟪b_i,x⟫=0` for `i > k`).
-- Summing the termwise bound over the orthonormal eigenbasis (`sum_sq_norm_inner_right`
-- collapses `∑‖⟪b_i,x⟫‖² = ‖x‖²`) yields the squared bound; `‖T x‖² = re⟪T†T x,x⟫`.
theorem s11655 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  intro x hx
  -- ‖T x‖² = re⟪(T†∘T) x, x⟫
  have hTx : ‖T x‖ ^ 2 = RCLike.re (inner 𝕜 ((LinearMap.adjoint T ∘ₗ T) x) x) := by
    rw [LinearMap.comp_apply, LinearMap.adjoint_inner_left, inner_self_eq_norm_sq]
  -- diagonalization of the Gram operator in its eigenbasis
  have h_id : RCLike.re (inner 𝕜 ((LinearMap.adjoint T ∘ₗ T) x) x)
      = ∑ i : Fin (Module.finrank 𝕜 E),
          T.isSymmetric_adjoint_comp_self.eigenvalues rfl i
            * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2 :=
    re_inner_symm_eq_sum_eigenvalues_2 (LinearMap.adjoint T ∘ₗ T)
      T.isSymmetric_adjoint_comp_self (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) x
  -- per-coordinate bound: σ_k² weight ≤ eigenvalue weight (orthogonality + antitone)
  have h_term : ∀ i : Fin (Module.finrank 𝕜 E),
      (T.singularValues k) ^ 2
          * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2
        ≤ T.isSymmetric_adjoint_comp_self.eigenvalues rfl i
          * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2 :=
    fun i => termwise_eigenvalue_bound T k hk x hx i
  -- assemble the squared bound
  have h_sq : (T.singularValues k) ^ 2 * ‖x‖ ^ 2 ≤ ‖T x‖ ^ 2 := by
    rw [hTx, h_id,
      ← (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl).sum_sq_norm_inner_right x,
      Finset.mul_sum]
    exact Finset.sum_le_sum fun i _ => h_term i
  -- squared → linear
  refine le_of_sq_le_sq ?_ (norm_nonneg (T x))
  rw [mul_pow]
  exact h_sq

end Problems.LinearAlgebra.eckart_young
