import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_exists_free_isometry_action_off_countable
import Problems.Geometry.banach_tarski.proofs.L_paradoxical_of_free_isometry_action

namespace Problems.Geometry.banach_tarski

-- Hausdorff→S²∖D paradox: split the assembly into the geometric "free action" half
-- and the abstract "transfer the F₂ paradox" half.
--   (A) exists_free_isometry_action_off_countable: build the F₂↪SO(3)↪(E≃ᵢE) embedding φ
--       (via orthogonal_matrix_isometry_equiv + freegroup_lift_injective) and take D = its
--       countable fixed-point set on S² (freegroup_range_countable +
--       rotation_fixed_set_on_sphere_finite + countable_fixed_set_of_pointwise_finite);
--       φ acts on S²∖D invariantly and FIXED-POINT-FREELY,
--       with 0∉D since D⊆S². All geometric bricks, no equidecomposition.
--   (B) paradoxical_of_free_isometry_action: GENERIC — a free, fixed-point-free, invariant
--       action of F₂ on M lifts the group paradox (rotation_subgroup_paradoxical/s11413) orbit-wise
--       to two Equidecomp pieces of M. No free-group/geometry specifics beyond φ.
-- Combinator: obtain D, φ + properties from (A); feed M := S²∖D, invariance and freeness to (B).
-- Each sub-goal is strictly simpler: (A) drops the equidecomposition layer; (B) drops all of the
-- sphere/fixed-point geometry.
theorem s11459 :
    ∃ D : Set E, D.Countable ∧ D ⊆ Metric.sphere (0 : E) 1 ∧ (0 : E) ∉ D ∧
      ∃ (f g : Equidecomp E (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = Metric.sphere (0 : E) 1 \ D ∧
        f.target = Metric.sphere (0 : E) 1 \ D ∧
        g.target = Metric.sphere (0 : E) 1 \ D  := by
  obtain ⟨D, φ, hDc, hDs, hD0, hφ, hinv, hfree⟩ :=
    exists_free_isometry_action_off_countable
  exact ⟨D, hDc, hDs, hD0,
    paradoxical_of_free_isometry_action φ hφ (Metric.sphere (0 : E) 1 \ D) hinv hfree⟩

end Problems.Geometry.banach_tarski
