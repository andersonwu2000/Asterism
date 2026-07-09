import Mathlib.Analysis.InnerProductSpace.Basic
import Library.Geometry.Manifold.DDZero
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.ManifoldBdry.PullbackFlatForm

/-!
# Section equality from coordinate agreement

This file proves that two smooth differential forms on a manifold are equal when their
coordinate representatives agree on every chart. The key ingredient is the injectivity of
the bundle trivialization at the basepoint, which lets us recover fibrewise equality from
equality of `formInCoord` reads.

## Main statements

- `fiber_eq_of_coord_at_basepoint`: if two forms have equal `formInCoord` values at the
  chart basepoint `extChartAt I p p`, then `α p = β p`.
- `fibrewise_eq_of_coord`: coordinate agreement on all charts implies pointwise fibre equality.
- `section_eq_of_coord`: coordinate agreement on all charts implies section equality.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.ManifoldBdry.PullbackFlatForm
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.SectionEqOfCoord

/-- Invert the basepoint trivialization read to recover fibrewise equality.

`formInCoord I γ p (extChartAt I p p)` is definitionally equal to
`Trivialization.continuousLinearMapAt ℝ (trivializationAt … p) p (γ p)`;
`key` rewrites the round-trip `p' = p` via `congrArg` over `hsymm`.
The hypothesis then equates the trivialization reads of `α p` and `β p`;
applying `Trivialization.symmL` to both sides and cancelling via
`symmL_continuousLinearMapAt` (valid since `p ∈ baseSet`) gives `α p = β p`. -/
theorem fiber_eq_of_coord_at_basepoint
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {m : ℕ} (α β : DiffForm I M m)
    (p : M)
    (hco : formInCoord I α p (extChartAt I p p) = formInCoord I β p (extChartAt I p p)) :
    α p = β p := by
  have hp : p ∈ (chartAt H p).source := mem_chart_source H p
  have hsymm : (extChartAt I p).symm (extChartAt I p p) = p :=
    (extChartAt I p).left_inv (by simpa only [extChartAt_source] using hp)
  have key : ∀ (γ : DiffForm I M m), formInCoord I γ p (extChartAt I p p)
      = Trivialization.continuousLinearMapAt ℝ
          (trivializationAt (E [⋀^Fin m]→L[ℝ] ℝ) (formBundleCore (M := M) I m).Fiber p)
          p (γ p) := fun γ =>
    congrArg
      (fun q : M => Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (E [⋀^Fin m]→L[ℝ] ℝ) (formBundleCore (M := M) I m).Fiber p)
        q (γ q)) hsymm
  rw [key α, key β] at hco
  have hsymmL := congrArg (Trivialization.symmL ℝ
    (trivializationAt (E [⋀^Fin m]→L[ℝ] ℝ) (formBundleCore (M := M) I m).Fiber p) p) hco
  rwa [Trivialization.symmL_continuousLinearMapAt _ hp,
       Trivialization.symmL_continuousLinearMapAt _ hp] at hsymmL

/-- Coordinate agreement on all charts implies pointwise fibre equality.

For each `p : M`, instantiate `h` at `x₀ = p` and `y = extChartAt I p p`
(the basepoint lies in the chart target by `mem_extChartAt_target`), giving coordinate
equality at the basepoint; `fiber_eq_of_coord_at_basepoint` then inverts the
trivialization read to recover `α p = β p`. -/
theorem fibrewise_eq_of_coord
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {m : ℕ} (α β : DiffForm I M m)
    (h : ∀ x₀ : M, ∀ y ∈ (extChartAt I x₀).target,
        formInCoord I α x₀ y = formInCoord I β x₀ y) :
    ∀ p : M, α p = β p := by
  intro p
  have hmem : extChartAt I p p ∈ (extChartAt I p).target := mem_extChartAt_target p
  have hco : formInCoord I α p (extChartAt I p p) = formInCoord I β p (extChartAt I p p) :=
    h p _ hmem
  exact fiber_eq_of_coord_at_basepoint I α β p hco

/-- Two differential forms agreeing on every chart-coordinate representative are equal.

Coordinate agreement gives pointwise fibre equality via `fibrewise_eq_of_coord`
(which uses trivialization injectivity at the basepoint), and `ContMDiffSection.ext`
lifts pointwise equality to section equality. -/
theorem section_eq_of_coord
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {m : ℕ} (α β : DiffForm I M m)
    (h : ∀ x₀ : M, ∀ y ∈ (extChartAt I x₀).target,
        formInCoord I α x₀ y = formInCoord I β x₀ y) :
    α = β := by
  have hpt := fibrewise_eq_of_coord I α β h
  exact ContMDiffSection.ext hpt

end Library.Geometry.ManifoldBdry.SectionEqOfCoord
