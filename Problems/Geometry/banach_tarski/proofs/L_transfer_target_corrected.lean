import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem transfer_target_corrected (h p : Equidecomp E (E ≃ᵢ E))
    (hpt : p.target = h.target) (hps : p.source ⊆ h.target) :
    (h.trans (p.trans h.symm)).target = h.source := by aesop

end Problems.Geometry.banach_tarski
