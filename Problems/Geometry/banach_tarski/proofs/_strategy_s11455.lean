import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_absorb_countable_paradoxical
import Problems.Geometry.banach_tarski.proofs.L_sphere_minus_fixed_paradoxical

namespace Problems.Geometry.banach_tarski

-- Hausdorff→sphere assembly: prove S² paradoxical by splitting at the countable
-- fixed-point set D of the F₂↪SO(3) free subgroup, then absorbing D back via Hilbert hotel.
-- Sub-goal (1) `sphere_minus_fixed_paradoxical`: ∃ countable D ⊆ S² with 0∉D such that S²∖D
--   is paradoxical — lifts the free-subgroup paradox (rotation_subgroup_paradoxical/s11413,
--   instantiated at H = E ≃ᵢ E) onto the free orbit of the embedded F₂, removing only the
--   countable fixed-point set D.
-- Sub-goal (2) `absorb_countable_paradoxical`: given any countable D ⊆ S² with 0∉D and S²∖D
--   paradoxical, transfer the paradox to all of S² — a rotation with pairwise-disjoint D-orbit
--   (exists_rotation_pairwise_disjoint_orbit_off_origin/3412) gives S² ≃ S²∖D, then compose
--   the equidecompositions via Equidecomp.trans.
-- Combinator: obtain ⟨D, …, hp⟩ from (1), feed to (2). Both sub-goals are strictly simpler —
-- (1) drops the absorption layer; (2) is a generic transfer with no free-group machinery.
theorem s11455 :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1  := by
  obtain ⟨D, hDc, hDs, hD0, hp⟩ := sphere_minus_fixed_paradoxical
  exact absorb_countable_paradoxical D hDc hDs hD0 hp

end Problems.Geometry.banach_tarski
