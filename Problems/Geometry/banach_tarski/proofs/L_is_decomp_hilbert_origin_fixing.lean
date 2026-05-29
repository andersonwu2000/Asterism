import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- is_decomp_hilbert_origin_fixing: piecewise map f (ρ on T, id elsewhere) witnesses
-- Equidecomp.IsDecompOn with witness set {ρ, 1}, both of which fix the origin.
theorem is_decomp_hilbert_origin_fixing (A T : Set E) (ρ : E ≃ᵢ E) (hρ0 : ρ 0 = 0) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S ∧ ∀ s ∈ S, s 0 = 0 := by
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  refine ⟨{ρ, 1}, ?_, ?_⟩
  · intro a _
    by_cases hT : a ∈ T
    · exact ⟨ρ, Finset.mem_insert_self ρ {1}, hf a hT⟩
    · exact ⟨1, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)),
        by rw [hf' a hT]; rfl⟩
  · intro s hs
    simp only [Finset.mem_insert, Finset.mem_singleton] at hs
    rcases hs with rfl | rfl
    · exact hρ0
    · rfl


end Problems.Geometry.banach_tarski
