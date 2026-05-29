import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_transfer_disjoint
import Problems.Geometry.banach_tarski.proofs.L_transfer_source
import Problems.Geometry.banach_tarski.proofs.L_transfer_union
import Problems.Geometry.banach_tarski.proofs.L_transfer_target_corrected

namespace Problems.Geometry.banach_tarski

-- Paradox transfers along equidecomposability: A ≃ B (via h) and B paradoxical ⇒ A paradoxical.
-- Same sandwich construction as the prior strategy (q := h.trans (p.trans h.symm)), but applies
-- the FIX for the lone dead sub-goal transfer_target: it needs the extra hypothesis p.source ⊆
-- h.target, which holds here since each B-piece source lies in f.source ∪ g.source = B = h.target.
-- Cites the three proved siblings (transfer_source/disjoint/union) directly; the single new
-- sub-goal transfer_target_corrected is transfer_target re-stated with the missing hps premise.
theorem s11468
    (A B : Set E) (h : Equidecomp E (E ≃ᵢ E)) (hsrc : h.source = A) (htgt : h.target = B)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)), Disjoint f.source g.source ∧
        f.source ∪ g.source = B ∧ f.target = B ∧ g.target = B) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)), Disjoint f.source g.source ∧
        f.source ∪ g.source = A ∧ f.target = A ∧ g.target = A  := by
  obtain ⟨f, g, hdisj, hunion, hftgt, hgtgt⟩ := hp
  have hft : f.target = h.target := hftgt.trans htgt.symm
  have hgt : g.target = h.target := hgtgt.trans htgt.symm
  have hfs : f.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_left
  have hgs : g.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_right
  refine ⟨h.trans (f.trans h.symm), h.trans (g.trans h.symm), ?_, ?_, ?_, ?_⟩
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_disjoint h f g hdisj
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_union A B h f g hsrc htgt hunion
  · rw [transfer_target_corrected h f hft hfs]; exact hsrc
  · rw [transfer_target_corrected h g hgt hgs]; exact hsrc

end Problems.Geometry.banach_tarski
