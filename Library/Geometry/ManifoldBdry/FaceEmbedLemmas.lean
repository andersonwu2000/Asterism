import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.MExtDerivCoord         -- formInCoord, instFormBundleContMDiff
import Library.Geometry.ManifoldBdry.BdryIsManifold      -- instBdryChartedSpace, isManifold_bdry
import Library.Geometry.ManifoldBdry.BdryValSmooth
import Library.Geometry.ManifoldBdry.PullbackBdryDefs
import Library.Geometry.ManifoldBoundary.CompactBdry     -- Bdry, TopologicalSpace
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.Calculus.FDeriv.Comp
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.Set.Basic
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.HasGroupoid
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.VectorBundle.Tangent
import Mathlib.Order.Filter.Basic
import Mathlib.Topology.Algebra.Module.Basic
import Mathlib.Topology.Basic

/-!
# Face embedding lemmas for manifolds with boundary

This file establishes the key analytic properties of `faceEmbed`, the linear embedding of
`EuclideanSpace ℝ (Fin n)` into `EuclideanHalfSpace (n + 1)` that identifies the boundary
face. The results cover pointwise equality with the bundled CLM `faceEmbedL`, Fréchet
differentiability, membership in the half-space range, and compatibility with extended charts.
These are used to relate the boundary transition maps to ambient-space transition maps when
computing the derivative of the coordinate-change on `Bdry n M`.

## Main results

- `faceEmbed_eq_faceEmbedL`: `faceEmbed z = faceEmbedL z` pointwise.
- `faceEmbed_hasFDerivAt`: `faceEmbed` has Fréchet derivative `faceEmbedL` everywhere.
- `faceEmbed_mem_range`: `faceEmbed z` lies in `Set.range (𝓡∂ (n + 1))`.
- `extChartAt_val_eq_faceEmbed_chartAt`: the ambient extended chart at a boundary point
  equals `faceEmbed` composed with the boundary chart.
- `extChartAt_trans_faceEmbed_eventuallyEq`: the ambient transition map agrees, near a
  boundary chart value, with `faceEmbed` of the boundary transition map.
- `bdry_trans_hasFDerivAt_coordChange`: the boundary transition map has derivative given by
  `tangentBundleCore.coordChange`.
- `faceEmbed_comp_bdry_trans_hasFDerivAt`: `faceEmbed` composed with the boundary transition
  map has the expected composed derivative.
- `extChartAt_trans_comp_faceEmbed_hasFDerivAt`: the ambient transition map precomposed with
  `faceEmbed` has the expected composed derivative.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.BdryValSmooth
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.FaceEmbedLemmas

variable {n : ℕ}

/-- `faceEmbed` equals the continuous linear map `faceEmbedL` applied pointwise.
Both are given by `∑ i, z i • basisFun i.succ`, so equality follows by unfolding. -/
theorem faceEmbed_eq_faceEmbedL (z : EuclideanSpace ℝ (Fin n)) :
    faceEmbed z = faceEmbedL (n := n) z := by
  simp only [faceEmbed, faceEmbedL, ContinuousLinearMap.sum_apply,
             ContinuousLinearMap.smulRight_apply]
  congr 1

/-- `faceEmbed` has Fréchet derivative `faceEmbedL` at every point of
`EuclideanSpace ℝ (Fin n)`, since it coincides with the continuous linear map `faceEmbedL`. -/
theorem faceEmbed_hasFDerivAt (z : EuclideanSpace ℝ (Fin n)) :
    HasFDerivAt faceEmbed (faceEmbedL (n := n)) z := by
  have heq : faceEmbed = ⇑(faceEmbedL (n := n)) := by
    ext w
    simp [faceEmbed, faceEmbedL, ContinuousLinearMap.smulRight_apply]
  rw [heq]
  exact faceEmbedL.hasFDerivAt

/-- `faceEmbed z` belongs to `Set.range (𝓡∂ (n + 1))`, the closed half-space.
This follows because `faceEmbed z` lies on the frontier of that range, and the range is closed. -/
theorem faceEmbed_mem_range (z : EuclideanSpace ℝ (Fin n)) :
    faceEmbed z ∈ Set.range (𝓡∂ (n + 1)) := by
  haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
  have hfr := faceEmbed_mem_frontier_range z
  have hclosed : IsClosed (Set.range (𝓡∂ (n + 1))) :=
    (𝓡∂ (n + 1)).isClosed_range
  exact hclosed.frontier_subset hfr

section ManifoldContext

variable {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- The ambient extended chart at a boundary point `p` equals `faceEmbed` applied to the
boundary chart value. Boundary points have zeroth ambient coordinate zero, so
`faceEmbed (faceProj y) = y` recovers the chart value. -/
theorem extChartAt_val_eq_faceEmbed_chartAt
    (p₀ p : Bdry n M)
    (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source) :
    extChartAt (𝓡∂ (n + 1)) p₀.val p.val =
      faceEmbed (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p) := by
  have hq : p.val ∈ (extChartAt (𝓡∂ (n + 1)) p₀.val).source := hp
  have h0 := Library.Geometry.ManifoldBoundary.BoundaryCoord.boundary_extChartAt_coord_zero
    p₀ p hq
  have heq : chartAt (EuclideanSpace ℝ (Fin n)) p₀ p =
      Library.Geometry.ManifoldBoundary.Defs.faceProj
        (extChartAt (𝓡∂ (n + 1)) p₀.val p.val) := rfl
  rw [heq]
  exact (Library.Geometry.ManifoldBoundary.BoundaryCoord.faceEmbed_faceProj_of_coord_zero
    _ h0).symm

/-- Near `chartAt p₀ p`, the function `z ↦ extChartAt p.val ((extChartAt p₀.val).symm (faceEmbed z))`
is eventually equal to `z ↦ faceEmbed ((chartAt p₀).symm ≫ₕ chartAt p) z)`.

The proof uses three steps: `hU` shows the overlap source is a neighbourhood; `hA` identifies
`(extChartAt p₀.val).symm ∘ faceEmbed` with the boundary inverse chart; `hB` applies
`extChartAt_val_eq_faceEmbed_chartAt` pointwise. -/
theorem extChartAt_trans_faceEmbed_eventuallyEq
    (p₀ p : Bdry n M)
    (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source) :
    (fun z => extChartAt (𝓡∂ (n + 1)) p.val
        ((extChartAt (𝓡∂ (n + 1)) p₀.val).symm (faceEmbed z)))
      =ᶠ[nhds (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p)]
      (fun z => faceEmbed (((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm ≫ₕ
        chartAt (EuclideanSpace ℝ (Fin n)) p) z)) := by
  have hU : ((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm ≫ₕ
      chartAt (EuclideanSpace ℝ (Fin n)) p).source ∈
      nhds (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p) := by
    refine ((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm ≫ₕ
      chartAt (EuclideanSpace ℝ (Fin n)) p).open_source.mem_nhds ?_
    rw [OpenPartialHomeomorph.trans_source, Set.mem_inter_iff,
      OpenPartialHomeomorph.symm_source]
    refine ⟨(chartAt (EuclideanSpace ℝ (Fin n)) p₀).map_source hp, ?_⟩
    rw [Set.mem_preimage, (chartAt (EuclideanSpace ℝ (Fin n)) p₀).left_inv hp]
    exact mem_chart_source (EuclideanSpace ℝ (Fin n)) p
  have hA : ∀ z ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).target,
      (extChartAt (𝓡∂ (n + 1)) p₀.val).symm (faceEmbed z)
        = ((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm z).val := fun z hz =>
    (Library.Geometry.ManifoldBdry.BdryChart.chartInvFun_val_eq_extChartAt_symm_faceEmbed
      p₀ z hz).symm
  have hB : ∀ x : Bdry n M, x ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p).source →
      extChartAt (𝓡∂ (n + 1)) p.val x.val
        = faceEmbed (chartAt (EuclideanSpace ℝ (Fin n)) p x) := by
    intro x hx
    have hsymm : (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p).symm
        (chartAt (EuclideanSpace ℝ (Fin n)) p x) = x := by
      have hred : (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p).symm
          (chartAt (EuclideanSpace ℝ (Fin n)) p x)
          = (chartAt (EuclideanSpace ℝ (Fin n)) p).symm
            (chartAt (EuclideanSpace ℝ (Fin n)) p x) := by
        simp only [extChartAt, OpenPartialHomeomorph.extend_coe_symm,
          modelWithCornersSelf_coe_symm, Function.comp_id]
      rw [hred]
      exact (chartAt (EuclideanSpace ℝ (Fin n)) p).left_inv hx
    have h := bdry_val_rep_eq_faceembed p (chartAt (EuclideanSpace ℝ (Fin n)) p x)
      ((chartAt (EuclideanSpace ℝ (Fin n)) p).map_source hx)
    rw [hsymm] at h
    exact h
  filter_upwards [hU] with z hz
  rw [OpenPartialHomeomorph.trans_source, Set.mem_inter_iff,
    OpenPartialHomeomorph.symm_source] at hz
  obtain ⟨hz₀, hz₁⟩ := hz
  rw [hA z hz₀, hB _ hz₁]
  rfl

/-- The boundary transition map `(chartAt p₀).symm ≫ₕ chartAt p` has Fréchet derivative
equal to `tangentBundleCore.coordChange` at `chartAt p₀ p`. -/
theorem bdry_trans_hasFDerivAt_coordChange
    (p₀ p : Bdry n M)
    (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source) :
    HasFDerivAt
      (fun z => ((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm ≫ₕ
        chartAt (EuclideanSpace ℝ (Fin n)) p) z)
      ((tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
        (achart (EuclideanSpace ℝ (Fin n)) p₀)
        (achart (EuclideanSpace ℝ (Fin n)) p) p)
      (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p) := by
  have hmem : p ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).source ∩
      (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p).source :=
    ⟨by rw [extChartAt_source]; exact hp,
     by rw [extChartAt_source]; exact mem_chart_source _ _⟩
  have h := hasFDerivWithinAt_tangentCoordChange (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) hmem
  rw [modelWithCornersSelf_coe, Set.range_id, hasFDerivWithinAt_univ] at h
  exact h

/-- `faceEmbed` composed with the boundary transition map has Fréchet derivative
`faceEmbedL.comp (tangentBundleCore.coordChange ...)` at `chartAt p₀ p`.
This follows by rewriting `faceEmbed` as `⇑faceEmbedL` and applying the CLM chain rule. -/
theorem faceEmbed_comp_bdry_trans_hasFDerivAt
    (p₀ p : Bdry n M)
    (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source) :
    HasFDerivAt
      (fun z => faceEmbed (((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm ≫ₕ
        chartAt (EuclideanSpace ℝ (Fin n)) p) z))
      (faceEmbedL.comp
        ((tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
          (achart (EuclideanSpace ℝ (Fin n)) p₀)
          (achart (EuclideanSpace ℝ (Fin n)) p) p))
      (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p) := by
  have h_eq : ∀ z : EuclideanSpace ℝ (Fin n),
      faceEmbed z = faceEmbedL (n := n) z :=
    fun z => faceEmbed_eq_faceEmbedL z
  have h_trans : HasFDerivAt
      (fun z => ((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm ≫ₕ
        chartAt (EuclideanSpace ℝ (Fin n)) p) z)
      ((tangentBundleCore 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M)).coordChange
        (achart (EuclideanSpace ℝ (Fin n)) p₀)
        (achart (EuclideanSpace ℝ (Fin n)) p) p)
      (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p) :=
    bdry_trans_hasFDerivAt_coordChange p₀ p hp
  have hfun : (fun z => faceEmbed (((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm ≫ₕ
        chartAt (EuclideanSpace ℝ (Fin n)) p) z))
      = (fun z => faceEmbedL (((chartAt (EuclideanSpace ℝ (Fin n)) p₀).symm ≫ₕ
        chartAt (EuclideanSpace ℝ (Fin n)) p) z)) :=
    funext fun z => h_eq _
  rw [hfun]
  exact faceEmbedL.hasFDerivAt.comp _ h_trans

/-- The ambient transition map precomposed with `faceEmbed` has Fréchet derivative
`(tangentBundleCore (𝓡∂ (n+1)) M).coordChange ... |>.comp faceEmbedL` at `chartAt p₀ p`.
The proof chains `hasFDerivWithinAt_tangentCoordChange` (for the ambient model) with
`faceEmbed_hasFDerivAt` via `HasFDerivWithinAt.comp_hasFDerivAt_of_eq`. -/
theorem extChartAt_trans_comp_faceEmbed_hasFDerivAt
    (p₀ p : Bdry n M)
    (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source) :
    HasFDerivAt
      (fun z => extChartAt (𝓡∂ (n + 1)) p.val
        ((extChartAt (𝓡∂ (n + 1)) p₀.val).symm (faceEmbed z)))
      (((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
          (achart (EuclideanHalfSpace (n + 1)) p₀.val)
          (achart (EuclideanHalfSpace (n + 1)) p.val) p.val).comp faceEmbedL)
      (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p) := by
  have h_src : p.val ∈ (extChartAt (𝓡∂ (n + 1)) p₀.val).source := by
    rw [extChartAt_source]
    exact (Set.mem_of_mem_inter_left hp)
  have h_within :
      HasFDerivWithinAt
        (extChartAt (𝓡∂ (n + 1)) p.val ∘ (extChartAt (𝓡∂ (n + 1)) p₀.val).symm)
        ((tangentBundleCore (𝓡∂ (n + 1)) M).coordChange
          (achart (EuclideanHalfSpace (n + 1)) p₀.val)
          (achart (EuclideanHalfSpace (n + 1)) p.val) p.val)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p₀.val p.val) :=
    hasFDerivWithinAt_tangentCoordChange ⟨h_src, mem_extChartAt_source _⟩
  have h_pt : extChartAt (𝓡∂ (n + 1)) p₀.val p.val =
      faceEmbed (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p) :=
    extChartAt_val_eq_faceEmbed_chartAt p₀ p hp
  have h_face : HasFDerivAt (faceEmbed (n := n)) faceEmbedL
      (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p) :=
    faceEmbed_hasFDerivAt (chartAt (EuclideanSpace ℝ (Fin n)) p₀ p)
  have h_range : ∀ z : EuclideanSpace ℝ (Fin n), faceEmbed z ∈ Set.range (𝓡∂ (n + 1)) :=
    fun z => faceEmbed_mem_range z
  exact h_within.comp_hasFDerivAt_of_eq _ h_face
    (Filter.Eventually.of_forall fun z => h_range z) h_pt

end ManifoldContext

end Library.Geometry.ManifoldBdry.FaceEmbedLemmas
