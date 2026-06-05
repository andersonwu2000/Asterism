import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- Spectral diagonalization of the Rayleigh form for a symmetric operator.
-- Expand ⟪T x, x⟫ over the eigenbasis via `sum_inner_mul_inner`; per term use
-- symmetry `⟪T x, bᵢ⟫ = ⟪x, T bᵢ⟫`, `T bᵢ = μᵢ • bᵢ`, and `conj z * z = ‖z‖²`,
-- then `re ∘ ofReal` collapses each real summand. Direct (no sub-goals).
theorem s11643 {𝕜 : Type*} [RCLike 𝕜] {E : Type*}
    [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (T : E →ₗ[𝕜] E) (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank 𝕜 E = n) (x : E) :
    RCLike.re (inner 𝕜 (T x) x)
      = ∑ i : Fin n, hT.eigenvalues hn i * ‖inner 𝕜 (hT.eigenvectorBasis hn i) x‖ ^ 2  := by
  classical
  rw [← OrthonormalBasis.sum_inner_mul_inner (hT.eigenvectorBasis hn) (T x) x, map_sum]
  apply Finset.sum_congr rfl
  intro i _
  rw [hT x (hT.eigenvectorBasis hn i), hT.apply_eigenvectorBasis hn i, inner_smul_right,
      ← inner_conj_symm, mul_assoc, RCLike.conj_mul,
      ← RCLike.ofReal_pow, ← RCLike.ofReal_mul, RCLike.ofReal_re]

end Problems.LinearAlgebra.eckart_young
