import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_rotation_fixed_set_on_sphere_finite
import Problems.Geometry.banach_tarski.proofs.L_free_so3_embedding

namespace Problems.Geometry.banach_tarski

-- Build φ as the LINEAR embedding ψ : F₂ →* (E ≃ₗᵢ[ℝ] E) post-composed with the
-- coercion homomorphism (·).toIsometryEquiv : (E ≃ₗᵢ[ℝ] E) →* (E ≃ᵢ E).
-- Sub-goal `free_so3_embedding` supplies ψ with: injectivity, and (per nontrivial word)
-- det = 1 and ψ w ≠ refl — the genuine SO(3) freeness/rotation content.
-- The remaining work is pure packaging: the coercion is an injective monoid hom
-- (so φ is injective), every ψ w is linear (so φ w fixes 0), and φ w x = x ⇔ ψ w x = x,
-- whence rotation_fixed_set_on_sphere_finite (proved sibling) gives the finite fixed set.
theorem s11470 :
    ∃ φ : FreeGroup (Fin 2) →* (E ≃ᵢ E),
      Function.Injective φ ∧
      (∀ w : FreeGroup (Fin 2), φ w 0 = 0) ∧
      (∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite)  := by
  obtain ⟨ψ, hinj, hprop⟩ := free_so3_embedding
  let c : (E ≃ₗᵢ[ℝ] E) →* (E ≃ᵢ E) :=
    { toFun := fun g => g.toIsometryEquiv
      map_one' := rfl
      map_mul' := fun a b => rfl }
  have hcinj : Function.Injective c := fun x y hxy =>
    LinearIsometryEquiv.toIsometryEquiv_injective hxy
  refine ⟨c.comp ψ, ?_, ?_, ?_⟩
  · exact hcinj.comp hinj
  · intro w
    change (ψ w).toIsometryEquiv 0 = 0
    simp
  · intro w hw
    obtain ⟨hdet, hne⟩ := hprop w hw
    have hfin := rotation_fixed_set_on_sphere_finite (ψ w) hdet hne
    convert hfin using 2

end Problems.Geometry.banach_tarski
