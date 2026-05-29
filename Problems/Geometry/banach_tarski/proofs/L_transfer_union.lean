import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- transfer_union: set-algebra close: distribute ∩ over ∪, preimage_union, hunion, map_source'
theorem transfer_union (A B : Set E) (h f g : Equidecomp E (E ≃ᵢ E))
    (hsrc : h.source = A) (htgt : h.target = B) (hunion : f.source ∪ g.source = B) :
    (h.source ∩ h ⁻¹' f.source) ∪ (h.source ∩ h ⁻¹' g.source) = A := by
  rw [← Set.inter_union_distrib_left, ← Set.preimage_union, hunion, ← htgt]
  ext x
  simp only [Set.mem_inter_iff, Set.mem_preimage]
  constructor
  · rintro ⟨hx, _⟩; rwa [hsrc] at hx
  · intro hx
    rw [← hsrc] at hx
    exact ⟨hx, h.map_source' hx⟩

end Problems.Geometry.banach_tarski