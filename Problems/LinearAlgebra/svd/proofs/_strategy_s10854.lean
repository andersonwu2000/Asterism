import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_exists_b_f_apply_eq
import Problems.LinearAlgebra.svd.proofs.L_matrix_eq_of_apply_eq

namespace Problems.LinearAlgebra.svd

-- Decompose into (A) existence of an orthonormal basis b_F of F such that
-- T(b_E i) expands as the i-th column of the target diagonal matrix in b_F
-- (the orthonormal-extension construction, using h_inner), and (B) a purely
-- mechanical translation from the column-expansion characterisation to the
-- toMatrix equality. (B) is a basis-representation unfolding free of any
-- geometry; (A) absorbs the construction work without needing the matrix
-- machinery, so each sub-goal is strictly simpler than the parent.
theorem s10854 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
      Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
        if (j : ℕ) = (i : ℕ)
        then ((T.singularValues i : ℝ) : 𝕜)
        else 0)  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner
  obtain ⟨b_F, hb_F⟩ := exists_b_f_apply_eq T b_E h_inner
  exact ⟨b_F, matrix_eq_of_apply_eq T b_E b_F hb_F⟩
end Problems.LinearAlgebra.svd
