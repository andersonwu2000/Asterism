import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_eigen_ge_low
import Problems.LinearAlgebra.eckart_young.proofs.L_inner_zero_high

namespace Problems.LinearAlgebra.eckart_young

-- Termwise σ_k²‖⟨b_i,x⟩‖² ≤ λ_i‖⟨b_i,x⟩‖²: split on (i:ℕ) ≤ k.
-- Low index (eigen_ge_low): σ_k² = λ_k ≤ λ_i, scale by nonneg ‖⟨b_i,x⟩‖².
-- High index (inner_zero_high): x in top-(k+1) span ⇒ ⟨b_i,x⟩ = 0, both sides vanish.
-- Sub-goals drop the sum/Parseval: a scalar comparison and a coordinate-vanishing fact.
theorem s11660 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (x : E) (hx : x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i)))) :
    ∀ i, (T.singularValues k)^2 * ‖inner 𝕜
        ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2
      ≤ (T.isSymmetric_adjoint_comp_self.eigenvalues
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2  := by
  intro i
  by_cases hi : (i : ℕ) ≤ k
  · -- low index: σ_k² = λ_k ≤ λ_i, scale by the nonneg coefficient ‖⟨b_i,x⟩‖²
    have hle : (T.singularValues k)^2 ≤ T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i := eigen_ge_low T k hk i hi
    exact mul_le_mul_of_nonneg_right hle (sq_nonneg _)
  · -- high index: x lies in the top-(k+1) span, so the coordinate ⟨b_i,x⟩ vanishes
    have hz : (inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x : 𝕜) = 0 :=
      inner_zero_high T k hk x hx i (by omega)
    rw [hz]
    simp

end Problems.LinearAlgebra.eckart_young
