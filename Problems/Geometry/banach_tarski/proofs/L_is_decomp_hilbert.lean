import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- is_decomp_hilbert: the piecewise map f (ρ on T, id elsewhere) witnesses Equidecomp.IsDecompOn
-- using witness set S = {ρ, 1} — each point in A is moved by ρ (if in T) or fixed by 1 (if not)
theorem is_decomp_hilbert (A T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S := by
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  refine ⟨{ρ, 1}, fun a _ => ?_⟩
  by_cases hT : a ∈ T
  · exact ⟨ρ, Finset.mem_insert_self ρ {1}, hf a hT⟩
  · exact ⟨1, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)),
      by rw [hf' a hT]; rfl⟩

end Problems.Geometry.banach_tarski


