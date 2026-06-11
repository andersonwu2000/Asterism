import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_bundle.proofs.L_alternatization_norm_le
import Problems.Geometry.stokes_form_bundle.proofs.L_alternatization_smul

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont

namespace Problems.Geometry.stokes_form_bundle

-- Bundle `ContinuousMultilinearMap.alternatization` (Mathlib has it only as `→+`) into a CLM
-- via `LinearMap.mkContinuous`: sub-goal `alternatization_smul` supplies ℝ-homogeneity (additivity
-- is Mathlib's `map_add`), sub-goal `alternatization_norm_le` supplies the operator bound
-- `‖alternatization m‖ ≤ (card ι)! * ‖m‖` (sum of (card ι)! sign-permuted copies of `m`).
-- The witness applies to `m` as `alternatization m` definitionally, so the ∀-clause is `rfl`.
theorem s11682
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι] :
    ∃ A : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G →L[ℝ] (E [⋀^ι]→L[ℝ] G),
      ∀ m, A m = ContinuousMultilinearMap.alternatization m  := by
  have h_smul : ∀ (c : ℝ) (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G),
      ContinuousMultilinearMap.alternatization (c • m)
        = c • ContinuousMultilinearMap.alternatization m :=
    fun c m ↦ alternatization_smul c m
  have h_bound : ∀ m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G,
      ‖(ContinuousMultilinearMap.alternatization m : E [⋀^ι]→L[ℝ] G)‖
        ≤ ((Nat.factorial (Fintype.card ι)) : ℝ) * ‖m‖ :=
    fun m ↦ alternatization_norm_le m
  refine ⟨LinearMap.mkContinuous
    { toFun := fun m ↦ ContinuousMultilinearMap.alternatization m
      map_add' := fun m₁ m₂ ↦ map_add _ m₁ m₂
      map_smul' := fun c m ↦ h_smul c m }
    ((Nat.factorial (Fintype.card ι)) : ℝ) h_bound, fun m ↦ rfl⟩
end Problems.Geometry.stokes_form_bundle
