import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_bundle.proofs.L_alternatization_pointwise_norm_le
import Problems.Geometry.stokes_form_bundle.proofs.L_alternatization_term_norm_le

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont

namespace Problems.Geometry.stokes_form_bundle

-- Reduce the operator-norm bound to a pointwise bound via ContinuousAlternatingMap.opNorm_le_bound.
-- alternatization m v = ∑ σ : Perm ι, sign σ • m (v ∘ σ) (alternatization_apply_apply), so the
-- pointwise value is a sum of (card ι)! terms each bounded by ‖m‖ * ∏ ‖v i‖: sub-goal
-- alternatization_term_norm_le bounds one sign-permuted term (sign is a unit, prod reindexes by σ);
-- sub-goal alternatization_pointwise_norm_le assembles the sum (norm_sum_le + Fintype.card_perm).
theorem s11683
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G) :
    ‖(ContinuousMultilinearMap.alternatization m : E [⋀^ι]→L[ℝ] G)‖
      ≤ ((Nat.factorial (Fintype.card ι)) : ℝ) * ‖m‖  := by
  refine ContinuousAlternatingMap.opNorm_le_bound _ (by positivity) fun v => ?_
  have h_term := alternatization_term_norm_le m
  have h_pointwise := alternatization_pointwise_norm_le m h_term
  exact h_pointwise v

end Problems.Geometry.stokes_form_bundle
