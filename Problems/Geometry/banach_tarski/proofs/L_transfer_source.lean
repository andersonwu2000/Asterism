import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- transfer_source: PartialEquiv.trans_source algebra — sandwich source = h.source ∩ h⁻¹'p.source
-- Unfolds Equidecomp.trans/symm to PartialEquiv, applies trans_source twice and symm_source,
-- then uses p.map_source' to discharge the extra p.target membership in the mpr direction.
theorem transfer_source (h p : Equidecomp E (E ≃ᵢ E)) (hpt : p.target = h.target) :
    (h.trans (p.trans h.symm)).source = h.source ∩ h ⁻¹' p.source := by
  simp only [Equidecomp.trans_toPartialEquiv, Equidecomp.symm_toPartialEquiv,
             PartialEquiv.trans_source, PartialEquiv.symm_source, ← hpt]
  ext x
  simp only [Set.mem_inter_iff, Set.mem_preimage]
  constructor
  · rintro ⟨hx_src, hx_h, _⟩
    exact ⟨hx_src, hx_h⟩
  · rintro ⟨hx_src, hx_h⟩
    exact ⟨hx_src, hx_h, p.map_source' hx_h⟩


end Problems.Geometry.banach_tarski
