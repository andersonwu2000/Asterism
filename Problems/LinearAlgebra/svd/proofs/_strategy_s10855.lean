import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_b_f_apply_eq_dite
import Problems.LinearAlgebra.svd.proofs.L_sum_ite_smul_eq_dite

namespace Problems.LinearAlgebra.svd

-- Decompose into (A) constructing b_F : OrthonormalBasis of F packaging the
-- orthonormal-extension construction, with per-index dite-form column property
-- (T(b_E i) = σ_i • b_F⟨i,_⟩ when (i:ℕ) < finrank F, else 0), and (B) a purely
-- algebraic identity collapsing the indicator-shaped sum to that dite. (A) absorbs
-- all geometric/construction work; (B) is T,b_E,h_inner-independent Finset.sum
-- manipulation. Combinator rewrites the parent sum via (B), then closes by (A).
theorem s10855 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ i, T (b_E i) = ∑ j : Fin (Module.finrank 𝕜 F),
      (if (j : ℕ) = (i : ℕ) then ((T.singularValues i : ℝ) : 𝕜) else 0) • b_F j := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner
  obtain ⟨b_F, h_col⟩ := b_f_apply_eq_dite T b_E h_inner
  refine ⟨b_F, fun i => ?_⟩
  rw [sum_ite_smul_eq_dite T b_E h_inner b_F i]
  exact h_col i

end Problems.LinearAlgebra.svd
