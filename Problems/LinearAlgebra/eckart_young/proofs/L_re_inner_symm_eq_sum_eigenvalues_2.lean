import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_re_inner_symm_eq_sum_eigenvalues

namespace Problems.LinearAlgebra.eckart_young

theorem re_inner_symm_eq_sum_eigenvalues_2 {𝕜 : Type*} [RCLike 𝕜] {E : Type*}
    [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (T : E →ₗ[𝕜] E) (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank 𝕜 E = n) (x : E) :
    RCLike.re (inner 𝕜 (T x) x)
      = ∑ i : Fin n, hT.eigenvalues hn i * ‖inner 𝕜 (hT.eigenvectorBasis hn i) x‖ ^ 2 := by apply re_inner_symm_eq_sum_eigenvalues <;> assumption

end Problems.LinearAlgebra.eckart_young
