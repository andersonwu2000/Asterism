import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- transfer_disjoint: preimage preserves disjointness; intersecting with h.source gives the result
theorem transfer_disjoint (h f g : Equidecomp E (E ≃ᵢ E))
    (hdisj : Disjoint f.source g.source) :
    Disjoint (h.source ∩ h ⁻¹' f.source) (h.source ∩ h ⁻¹' g.source) := by
  exact (hdisj.preimage h).mono Set.inter_subset_right Set.inter_subset_right

end Problems.Geometry.banach_tarski
