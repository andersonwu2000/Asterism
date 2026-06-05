import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_norm_sq_eq_sum_repr_sq_2
import Problems.LinearAlgebra.courant_fischer.proofs.L_numerator_eigenbasis_expand
import Problems.LinearAlgebra.courant_fischer.proofs.L_weighted_eigenvalue_sum_ge

namespace Problems.LinearAlgebra.courant_fischer

-- Rayleigh numerator bound: expand both sides in the orthonormal eigenbasis.
-- (1) ⟪Tx,x⟫ = ∑ λᵢ·(repr x i)²  (numerator_eigenbasis_expand);
-- (2) ‖x‖² = ∑ (repr x i)²        (norm_sq_eq_sum_repr_sq_2);
-- (3) with the high modes (i>k) vanishing, antitone spectrum gives the
--     termwise/summed bound λ_k·∑(repr)² ≤ ∑ λᵢ·(repr)² (weighted_eigenvalue_sum_ge).
-- Rewrite by (1),(2) and close with (3).
theorem s11632
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (x : E)
    (hv : ∀ i : Fin n, (k : ℕ) < (i : ℕ) →
      (hT.eigenvectorBasis hn).repr x i = 0) :
    hT.eigenvalues hn k * ‖x‖ ^ 2 ≤ @inner ℝ E _ (T x) x  := by
  have h_num : (inner ℝ (T x) x : ℝ) =
      ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    numerator_eigenbasis_expand hT hn x
  have h_norm : ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    norm_sq_eq_sum_repr_sq_2 hT hn x
  have h_sum : hT.eigenvalues hn k * (∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2)
      ≤ ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    weighted_eigenvalue_sum_ge hT hn k x hv
  rw [h_num, h_norm]
  exact h_sum
end Problems.LinearAlgebra.courant_fischer
