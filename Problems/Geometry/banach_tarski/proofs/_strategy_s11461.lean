import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_transfer_disjoint
import Problems.Geometry.banach_tarski.proofs.L_transfer_source
import Problems.Geometry.banach_tarski.proofs.L_transfer_target
import Problems.Geometry.banach_tarski.proofs.L_transfer_union

namespace Problems.Geometry.banach_tarski

-- Paradox transfers along equidecomposability: A ≃ B (via h) and B paradoxical ⇒ A paradoxical.
-- Construction: sandwich each B-piece p between h and h.symm — q := h.trans (p.trans h.symm)
-- realizes A ≃ B ≃ (p-piece) ≃ B ≃ A, giving an A-piece with source h.source ∩ h⁻¹'p.source.
-- Sub-goals (all fully abstract over sets/Equidecomp, no geometry/free-group machinery):
--   transfer_source/transfer_target compute the sandwich's source/target (the only Equidecomp
--   trans/symm algebra); transfer_disjoint/transfer_union are pure set algebra on the resulting
--   sources (preimage preserves disjointness; the two sources cover h.source = A via map_source').
theorem s11461
    (A B : Set E) (h : Equidecomp E (E ≃ᵢ E)) (hsrc : h.source = A) (htgt : h.target = B)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)), Disjoint f.source g.source ∧
        f.source ∪ g.source = B ∧ f.target = B ∧ g.target = B) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)), Disjoint f.source g.source ∧
        f.source ∪ g.source = A ∧ f.target = A ∧ g.target = A  := by
  obtain ⟨f, g, hdisj, hunion, hftgt, hgtgt⟩ := hp
  have hft : f.target = h.target := hftgt.trans htgt.symm
  have hgt : g.target = h.target := hgtgt.trans htgt.symm
  refine ⟨h.trans (f.trans h.symm), h.trans (g.trans h.symm), ?_, ?_, ?_, ?_⟩
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_disjoint h f g hdisj
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_union A B h f g hsrc htgt hunion
  · rw [transfer_target h f hft]; exact hsrc
  · rw [transfer_target h g hgt]; exact hsrc

end Problems.Geometry.banach_tarski
