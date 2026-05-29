import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem transfer_target (h p : Equidecomp E (E ≃ᵢ E)) (hpt : p.target = h.target) :
    (h.trans (p.trans h.symm)).target = h.source := by sorry

end Problems.Geometry.banach_tarski
