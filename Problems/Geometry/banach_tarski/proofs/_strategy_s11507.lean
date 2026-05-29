import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_paradoxical_transfer_along_equidecomp_origin_fixing
import Problems.Geometry.banach_tarski.proofs.L_sphere_hilbert_hotel_absorb_origin_fixing

namespace Problems.Geometry.banach_tarski

-- Mirror the proved non-origin-fixing absorption (s11458) but thread the origin-fixing
-- IsDecompOn data: (1) an origin-fixing Hilbert-hotel absorption equidecomp h : S² ≃ S²∖D
-- (rotation ρ and ρ⁻¹ fix 0, so both h and h.symm have origin-fixing decomp sets), then
-- (2) a generic transfer that carries a B-paradox with origin-fixing data to A preserving it.
theorem s11507
    (D : Set E) (hDc : D.Countable) (hDs : D ⊆ Metric.sphere (0 : E) 1)
    (hD0 : (0 : E) ∉ D)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = Metric.sphere (0 : E) 1 \ D ∧
        f.target = Metric.sphere (0 : E) 1 \ D ∧
        g.target = Metric.sphere (0 : E) 1 \ D ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨h, Sh, Sh', hsrc, htgt, hdec_h, hdec_h', h0h, h0h'⟩ :=
    sphere_hilbert_hotel_absorb_origin_fixing D hDc hDs hD0
  exact paradoxical_transfer_along_equidecomp_origin_fixing
    (Metric.sphere (0 : E) 1) (Metric.sphere (0 : E) 1 \ D)
    h Sh Sh' hsrc htgt hdec_h hdec_h' h0h h0h' hp



end Problems.Geometry.banach_tarski
