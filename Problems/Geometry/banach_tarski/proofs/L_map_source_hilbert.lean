import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- map_source_hilbert: abstract Hilbert-hotel piecewise map sends A into A \ D
-- Case x∈T: f x = ρ x ∈ ρ''T = T\D ⊆ A\D. Case x∉T: f x = x ∉ D (since D⊆T).
theorem map_source_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hDT : D ⊆ T) (hTA : T ⊆ A) (hshift : ρ '' T = T \ D) :
    ∀ x ∈ A, f x ∈ A \ D := by
  intro x hxA
  by_cases hxT : x ∈ T
  · rw [hf x hxT]
    have hmem : ρ x ∈ ρ '' T := Set.mem_image_of_mem _ hxT
    rw [hshift] at hmem
    exact ⟨hTA hmem.1, hmem.2⟩
  · rw [hf' x hxT]
    exact ⟨hxA, fun hxD => hxT (hDT hxD)⟩

end Problems.Geometry.banach_tarski
