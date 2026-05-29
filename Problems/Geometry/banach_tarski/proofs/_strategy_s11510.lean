import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_transfer_source
import Problems.Geometry.banach_tarski.proofs.L_transfer_disjoint
import Problems.Geometry.banach_tarski.proofs.L_transfer_union
import Problems.Geometry.banach_tarski.proofs.L_transfer_target_corrected
import Problems.Geometry.banach_tarski.proofs.L_decomp_trans_origin_fixing

namespace Problems.Geometry.banach_tarski

-- Mirror the proved non-origin-fixing transfer s11468 (q := h.trans (f.trans h.symm)), reusing
-- transfer_source/disjoint/union/target_corrected for the source/target/disjoint/union parts.
-- New content is the origin-fixing decomp data: decomp_trans_origin_fixing composes two
-- origin-fixing IsDecompOn finsets into one for an Equidecomp.trans; apply it twice
-- (f.trans h.symm, then h.trans …) to get Sf'/Sg' fixing 0 (each factor is a product of fixers).
theorem s11510
    (A B : Set E) (h : Equidecomp E (E ≃ᵢ E)) (Sh Sh' : Finset (E ≃ᵢ E))
    (hsrc : h.source = A) (htgt : h.target = B)
    (hdec_h : Equidecomp.IsDecompOn h.toFun h.source Sh)
    (hdec_h' : Equidecomp.IsDecompOn h.symm.toFun h.symm.source Sh')
    (h0h : ∀ s ∈ Sh, s 0 = 0) (h0h' : ∀ s ∈ Sh', s 0 = 0)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = B ∧
        f.target = B ∧ g.target = B ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = A ∧
      f.target = A ∧ g.target = A ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨f, g, Sf, Sg, hdisj, hunion, hftgt, hgtgt, hdec_f, hdec_g, h0f, h0g⟩ := hp
  have hft : f.target = h.target := hftgt.trans htgt.symm
  have hgt : g.target = h.target := hgtgt.trans htgt.symm
  have hfs : f.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_left
  have hgs : g.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_right
  obtain ⟨Sfh, hdec_fh, h0fh⟩ :=
    decomp_trans_origin_fixing f h.symm Sf Sh' hdec_f hdec_h' h0f h0h'
  obtain ⟨Sf', hdec_f', h0f'⟩ :=
    decomp_trans_origin_fixing h (f.trans h.symm) Sh Sfh hdec_h hdec_fh h0h h0fh
  obtain ⟨Sgh, hdec_gh, h0gh⟩ :=
    decomp_trans_origin_fixing g h.symm Sg Sh' hdec_g hdec_h' h0g h0h'
  obtain ⟨Sg', hdec_g', h0g'⟩ :=
    decomp_trans_origin_fixing h (g.trans h.symm) Sh Sgh hdec_h hdec_gh h0h h0gh
  refine ⟨h.trans (f.trans h.symm), h.trans (g.trans h.symm), Sf', Sg',
    ?_, ?_, ?_, ?_, hdec_f', hdec_g', h0f', h0g'⟩
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_disjoint h f g hdisj
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_union A B h f g hsrc htgt hunion
  · rw [transfer_target_corrected h f hft hfs]; exact hsrc
  · rw [transfer_target_corrected h g hgt hgs]; exact hsrc


end Problems.Geometry.banach_tarski
