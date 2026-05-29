import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_absorb_countable_paradoxical_origin_fixing
import Problems.Geometry.banach_tarski.proofs.L_sphere_minus_fixed_paradoxical_origin_fixing

namespace Problems.Geometry.banach_tarski

-- Strengthen the proved sphere paradox (s11455) with origin-fixing witnessing data,
-- mirroring its two-layer structure but threading the IsDecompOn sets Sf/Sg whose
-- isometries all fix 0 (the F₂↪SO(3) generators and the absorption rotation are rotations).
-- (1) sphere_minus_fixed_paradoxical_origin_fixing: the free-action paradox of S²∖D with
--     origin-fixing decomposition sets — drops the absorption layer.
-- (2) absorb_countable_paradoxical_origin_fixing: transfer the S²∖D paradox to S² preserving
--     the origin-fixing data — generic Hilbert-hotel absorption, no free-group machinery.
-- Combinator: obtain D + the strengthened paradox from (1), feed to (2).
theorem s11503 :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨D, hDc, hDs, hD0, hp⟩ := sphere_minus_fixed_paradoxical_origin_fixing
  exact absorb_countable_paradoxical_origin_fixing D hDc hDs hD0 hp


end Problems.Geometry.banach_tarski
