import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- equidecomp_trans_glue: Equidecomp.trans packages two composable equidecompositions
-- into one with source = e₁.source and target = e₂.target, given e₁.target = e₂.source.
-- entry_kind: Builder
theorem equidecomp_trans_glue
    (e₁ e₂ : Equidecomp E (E ≃ᵢ E)) (h : e₁.target = e₂.source) :
    ∃ e : Equidecomp E (E ≃ᵢ E), e.source = e₁.source ∧ e.target = e₂.target := by
  refine ⟨e₁.trans e₂, ?_, ?_⟩
  · simp only [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source]
    rw [← h]
    ext x
    simp only [Set.mem_inter_iff, Set.mem_preimage]
    constructor
    · intro ⟨hx, _⟩; exact hx
    · intro hx
      exact ⟨hx, e₁.map_source' hx⟩
  · simp only [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_target]
    rw [h]
    ext x
    simp only [Set.mem_inter_iff, Set.mem_preimage]
    constructor
    · intro ⟨hx, _⟩; exact hx
    · intro hx
      exact ⟨hx, e₂.map_target' hx⟩

end Problems.Geometry.banach_tarski
