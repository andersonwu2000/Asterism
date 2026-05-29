import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- t_conj_via_prodequiv: T equals its conjugate by prodEquivOfIsCompl — block-diagonal form
-- Proves T = e ∘ prodMap(T|W, T|W') ∘ e⁻¹ where e : W × W' ≃ₗ F is the IsCompl equivalence,
-- by showing T ∘ e = e ∘ prodMap (since T preserves W and W') then canceling e on the right.
-- entry_kind: Builder
theorem t_conj_via_prodequiv
    {𝕜 : Type*} [Field 𝕜] {F : Type*} [AddCommGroup F] [Module 𝕜 F]
    (T : F →ₗ[𝕜] F) (W W' : Submodule 𝕜 F)
    (hW : ∀ x ∈ W, T x ∈ W) (hW' : ∀ x ∈ W', T x ∈ W')
    (hcompl : IsCompl W W') :
    T = (Submodule.prodEquivOfIsCompl W W' hcompl).toLinearMap.comp
        ((LinearMap.prodMap (T.restrict hW) (T.restrict hW')).comp
          (Submodule.prodEquivOfIsCompl W W' hcompl).symm.toLinearMap) := by
  set e := W.prodEquivOfIsCompl W' hcompl
  set f := (T.restrict hW).prodMap (T.restrict hW')
  have hcomp : T.comp e.toLinearMap = e.toLinearMap.comp f := by
    apply LinearMap.ext
    rintro ⟨⟨w, hw⟩, ⟨w', hw'⟩⟩
    simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap]
    simp only [f, LinearMap.prodMap_apply, LinearMap.restrict_apply]
    change T (w + w') = T w + T w'
    exact map_add T w w'
  ext x
  have hx : T x = T (e (e.symm x)) := by rw [e.apply_symm_apply]
  rw [hx]
  have h2 : T (e (e.symm x)) = e (f (e.symm x)) := by
    have := congr($(hcomp) (e.symm x))
    simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap] at this
    exact this
  simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap, h2]

end Problems.Geometry.banach_tarski