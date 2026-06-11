import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont

namespace Problems.Geometry.stokes_form_bundle

-- alternatization_smul: ContinuousMultilinearMap.alternatization is ℝ-homogeneous;
-- proved by ext + simp using alternatization_apply_apply, smul_apply, Finset.smul_sum,
-- and smul_comm to push the ℝ-scalar past the ℤˣ sign factor.
theorem alternatization_smul
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (c : ℝ) (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G) :
    ContinuousMultilinearMap.alternatization (c • m)
      = c • ContinuousMultilinearMap.alternatization m := by
  ext v
  simp only [ContinuousMultilinearMap.alternatization_apply_apply,
    ContinuousAlternatingMap.smul_apply, ContinuousMultilinearMap.smul_apply,
    Finset.smul_sum, smul_comm c]

end Problems.Geometry.stokes_form_bundle
