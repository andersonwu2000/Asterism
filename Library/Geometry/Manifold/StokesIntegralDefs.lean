import Library.Geometry.Manifold.DiffFormBundle    -- DiffForm
import Library.Geometry.Manifold.MExtDerivCoord     -- formInCoord
import Mathlib

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.StokesIntegralDefs

/-- An **orientation** of a manifold `N` modelled on `EuclideanSpace ℝ (Fin d)`: a
    chosen nowhere-zero reference top `d`-form. General over the model `I`, so it
    serves both `M` (`𝓡∂ (n+1)`) and its boundary (`𝓘(ℝ, EuclideanSpace (Fin n))`). -/
class OrientedManifold {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    (I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH)
    (N : Type*) [TopologicalSpace N] [ChartedSpace EH N] [IsManifold I ∞ N] where
  /-- The chosen nowhere-zero reference top form orienting `N`. -/
  refForm : DiffForm I N d
  /-- The reference form vanishes nowhere. -/
  refForm_ne : ∀ x : N, refForm x ≠ 0

variable {d : ℕ} {EH : Type*} [TopologicalSpace EH]
  {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
  {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
  [IsManifold I ∞ N] [CompactSpace N]

variable {d : ℕ} {EH : Type*} [TopologicalSpace EH]
  {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
  {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
  [IsManifold I ∞ N] [CompactSpace N]

/-- Coefficient of a top alternating form on the standard basis of `EuclideanSpace ℝ (Fin d)`. -/
noncomputable def topCoeff
    (α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ) : ℝ :=
  α (EuclideanSpace.basisFun (Fin d) ℝ)

/-- Local scalar density of a top form `φ` in the chart at `x`. -/
noncomputable def localCoeff (φ : DiffForm I N d) (x : N) :
    EuclideanSpace ℝ (Fin d) → ℝ :=
  fun y => topCoeff (formInCoord I φ x y)

/-- `∫_N φ` — integral of a top `d`-form over the oriented compact manifold `N`:
    partition-of-unity sum of the chart-localised coefficient, weighted by the
    per-chart orientation sign read from the reference form `μ`. THE canonical
    integration operator — both sides of Stokes use it. -/
noncomputable def DiffForm.integral [OrientedManifold I N] (φ : DiffForm I N d) : ℝ :=
  let μ := OrientedManifold.refForm (I := I) (N := N)
  let h := SmoothBumpCovering.exists_isSubordinate
    (I := I) (M := N) (s := Set.univ) isClosed_univ
    (U := fun x => (chartAt EH x).source)
    (fun x _ => (chartAt EH x).open_source.mem_nhds (mem_chart_source _ x))
  let B := h.choose_spec.choose
  ∑ᶠ i, ∫ y in (extChartAt I (B.c i)).target,
    B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
      * localCoeff φ (B.c i) y
      * Real.sign (localCoeff μ (B.c i) y) ∂volume

end Library.Geometry.Manifold.StokesIntegralDefs
