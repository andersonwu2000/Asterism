import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs

namespace Problems.LinearAlgebra.polar_decomposition

-- Direct proof: two linear maps on E agree iff they agree on the basis b_E.
-- `Basis.ext` reduces to a pointwise check; `constr` sends b_E i ↦ σ_i • b_E i,
-- the isometry equiv sends that to σ_i • b_F i (equiv_apply_basis), and h_col
-- gives T (b_E i) = σ_i • b_F i. No sub-goals needed.
theorem s11549 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_col : ∀ i, T (b_E i) = if h : (i : ℕ) < (Module.finrank 𝕜 E)
      then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
      else 0),
  T = (b_E.equiv b_F (Equiv.refl _)).toLinearMap ∘ₗ
  b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)  := by
  intro 𝕜 _ E _ _ _ T b_E b_F h_col
  apply b_E.toBasis.ext
  intro i
  simp only [OrthonormalBasis.coe_toBasis, LinearMap.comp_apply]
  rw [h_col i, dif_pos i.isLt]
  simp [OrthonormalBasis.equiv_apply_basis]
end Problems.LinearAlgebra.polar_decomposition
