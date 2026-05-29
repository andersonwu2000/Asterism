import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- left_inv_hilbert: g∘f = id on A; case-split on T membership using ρ''T = T\D ⊆ T
theorem left_inv_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f g : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (hshift : ρ '' T = T \ D) :
    ∀ x ∈ A, g (f x) = x := by
  intro x _
  by_cases hxT : x ∈ T
  · rw [hf x hxT]
    have hρxT : ρ x ∈ T := by
      have hmem : ρ x ∈ ρ '' T := Set.mem_image_of_mem _ hxT
      rw [hshift] at hmem
      exact hmem.1
    rw [hg (ρ x) hρxT]
    exact ρ.symm_apply_apply x
  · rw [hf' x hxT, hg' x hxT]

end Problems.Geometry.banach_tarski
