import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- letter0_is_decomp: piecewise map (id on A, g0•· elsewhere) witnesses IsDecompOn via {1, g0}
theorem letter0_is_decomp
    (A B : Set E) (g0 : E ≃ᵢ E) (f : E → E)
    (hAB : Disjoint A B)
    (hfA : ∀ x ∈ A, f x = x)
    (hfnA : ∀ x, x ∉ A → f x = g0 • x) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f (A ∪ B) S := by
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  refine ⟨{1, g0}, fun a _ => ?_⟩
  by_cases hA : a ∈ A
  · exact ⟨1, Finset.mem_insert_self 1 {g0}, by rw [hfA a hA]; simp⟩
  · exact ⟨g0, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)), hfnA a hA⟩

end Problems.Geometry.banach_tarski