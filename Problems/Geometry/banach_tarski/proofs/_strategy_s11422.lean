import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_t_conj_via_prodequiv

namespace Problems.Geometry.banach_tarski

-- Block-diagonal determinant: F = W ⊕ W' with both T-invariant, so in a basis
-- adapted to the decomposition T is block-diagonal, giving det T = det(T|W)·det(T|W').
-- Realize this as conjugation by `Submodule.prodEquivOfIsCompl`: the sub-goal
-- `t_conj_via_prodequiv` says T equals e ∘ (T|W ×ₗ T|W') ∘ e.symm; then
-- `LinearMap.det_conj` strips the conjugation and `LinearMap.det_prodMap` splits the product.
theorem s11422
    {𝕜 : Type*} [Field 𝕜] {F : Type*} [AddCommGroup F] [Module 𝕜 F]
    [FiniteDimensional 𝕜 F]
    (T : F →ₗ[𝕜] F) (W W' : Submodule 𝕜 F)
    (hW : ∀ x ∈ W, T x ∈ W) (hW' : ∀ x ∈ W', T x ∈ W')
    (hbot : W ⊓ W' = ⊥) (htop : W ⊔ W' = ⊤) :
    LinearMap.det T
      = LinearMap.det (T.restrict hW) * LinearMap.det (T.restrict hW')  := by
  have hcompl : IsCompl W W' := ⟨disjoint_iff.mpr hbot, codisjoint_iff.mpr htop⟩
  have h_conj := t_conj_via_prodequiv T W W' hW hW' hcompl
  conv_lhs => rw [h_conj]
  rw [LinearMap.det_conj, LinearMap.det_prodMap]

end Problems.Geometry.banach_tarski
