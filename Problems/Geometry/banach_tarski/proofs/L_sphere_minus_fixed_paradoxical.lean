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
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11459

namespace Problems.Geometry.banach_tarski

def sphere_minus_fixed_paradoxical := @Problems.Geometry.banach_tarski.s11459

end Problems.Geometry.banach_tarski
