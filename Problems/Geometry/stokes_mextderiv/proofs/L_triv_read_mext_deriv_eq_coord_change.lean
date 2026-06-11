import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FormCoordChange

-- triv_read_mext_deriv_eq_coord_change: trivializationAt read of mextDerivFun equals
-- formCoordChange applied to the model-space extDerivWithin, via symmL identity
-- (trivializationAt_symmL + coordChange_self) and localTriv_apply (rfl).
theorem triv_read_mext_deriv_eq_coord_change
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ x : M) :
    ((trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
        (formBundleCore (M := M) I (k + 1)).Fiber x₀) ⟨x, mextDerivFun I φ x⟩).2
      = formCoordChange I (k + 1) (achart H x) (achart H x₀) x
    (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x)) := by
  simp only [mextDerivFun]
  -- (trivAt x).symmL ℝ x = coordChange (i x) (i x) x (trivializationAt_symmL)
  have hmem : x ∈ (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
      (formBundleCore (M := M) I (k + 1)).Fiber x).baseSet :=
    (formBundleCore (M := M) I (k + 1)).mem_localTrivAt_baseSet x
  have hfun : (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
      (formBundleCore (M := M) I (k + 1)).Fiber x).symmL ℝ x =
      (formBundleCore (M := M) I (k + 1)).coordChange
        ((formBundleCore (M := M) I (k + 1)).indexAt x)
        ((formBundleCore (M := M) I (k + 1)).indexAt x) x :=
    (formBundleCore (M := M) I (k + 1)).trivializationAt_symmL hmem
  rw [hfun]
  -- (trivAt x₀ ⟨x, z⟩).2 = formCoordChange (achart H x) (achart H x₀) x z by rfl
  have step1 : ∀ (z : (formBundleCore (M := M) I (k + 1)).Fiber x),
      ((trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
          (formBundleCore (M := M) I (k + 1)).Fiber x₀) ⟨x, z⟩).2 =
        formCoordChange I (k + 1) (achart H x) (achart H x₀) x z := fun _ => rfl
  rw [step1]
  -- Simplify coordChange i i x v = v via coordChange_self
  have hself :
      (formBundleCore (M := M) I (k + 1)).coordChange
        ((formBundleCore (M := M) I (k + 1)).indexAt x)
        ((formBundleCore (M := M) I (k + 1)).indexAt x) x
        (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x)) =
      extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x) :=
    (formBundleCore (M := M) I (k + 1)).coordChange_self
      ((formBundleCore (M := M) I (k + 1)).indexAt x) x
      ((formBundleCore (M := M) I (k + 1)).mem_baseSet_at x)
      (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))
  exact congrArg (formCoordChange I (k + 1) (achart H x) (achart H x₀) x) hself
end Problems.Geometry.stokes_mextderiv
