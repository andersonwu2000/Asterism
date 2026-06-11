import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FormCoordChange

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

-- Direct proof (no sub-goals): the identity is definitional bookkeeping.
-- `hp` gives `(extChartAt I x).symm (extChartAt I x p) = p` via `left_inv`; transporting
-- that along the constant-fiber read `q ↦ continuousLinearMapAt ℝ e q (φ q)` (congrArg,
-- since the dependent rewrite is blocked by `q` in the fiber type) reduces `formInCoord`
-- to the trivialization read at `p`; `continuousLinearMapAt_apply_of_mem` turns it into
-- the raw pair read, which is `formCoordChange I k (achart H p) (achart H x) p (φ p)`
-- by `rfl` (`formBundleCore.coordChange = formCoordChange`, `indexAt = achart`).
theorem s11689 {k : ℕ} (φ : DiffForm I M k) (x : M)
    {p : M} (hp : p ∈ (chartAt H x).source) :
    formInCoord I φ x (extChartAt I x p)
      = formCoordChange I k (achart H p) (achart H x) p (φ p)  := by
  have hsymm : (extChartAt I x).symm (extChartAt I x p) = p :=
    (extChartAt I x).left_inv (by simpa only [extChartAt_source] using hp)
  have key : formInCoord I φ x (extChartAt I x p)
      = Trivialization.continuousLinearMapAt ℝ
          (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x)
          p (φ p) :=
    congrArg
      (fun q : M => Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x)
        q (φ q)) hsymm
  rw [key, Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hp]
  rfl

end Problems.Geometry.stokes_mextderiv
