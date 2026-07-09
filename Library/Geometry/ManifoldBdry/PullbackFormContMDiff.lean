import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.FormCoordChangeSelf
import Library.Geometry.Manifold.MExtDerivCoord         -- formInCoord, instFormBundleContMDiff
import Library.Geometry.ManifoldBdry.BdryIsManifold      -- instBdryChartedSpace, isManifold_bdry
import Library.Geometry.ManifoldBdry.BdryValSmooth
import Library.Geometry.ManifoldBdry.FaceEmbedLemmas
import Library.Geometry.ManifoldBdry.PullbackBdryDefs
import Library.Geometry.ManifoldBoundary.CompactBdry     -- Bdry, TopologicalSpace
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.ContDiff.Operations
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Data.Set.Function
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.ContMDiff.NormedSpace
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.VectorBundle.Basic
import Mathlib.Topology.Basic
import Mathlib.Topology.FiberBundle.Basic

/-!
# Smoothness of the boundary pullback of differential forms

This file proves that the pullback of a smooth differential form along the boundary
inclusion `Bdry n M → M` is itself a smooth section of the appropriate form bundle over
`Bdry n M`.

## Main statements

- `pullback_triv_read`: the trivialization of the pullback section in a fixed chart equals
  `compContinuousLinearMapCLM faceEmbedL` applied to the form's coordinate representative.
- `pullback_fixed_chart_contmdiff_at`: the fixed-basepoint coordinate formula for the
  pullback is smooth at every boundary point.
- `contMDiff_pullbackBdryFun`: the pullback section `pullbackBdryFun φ` is smooth as a map
  into the total space of the form bundle over `Bdry n M`.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.BdryValSmooth
open Library.Geometry.ManifoldBdry.FaceEmbedLemmas
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.PullbackFormContMDiff

/-- Transport the basepoint of `formInCoord` using `formCoordChange` at `x`, cancelling the
self-transition via `formCoordChange_self`. -/
theorem form_coord_change_transport_self
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ x : M)
    (hx : x ∈ (chartAt H x₀).source) :
    formCoordChange I k (achart H x) (achart H x₀) x
        (formInCoord I φ x (extChartAt I x x))
      = formInCoord I φ x₀ (extChartAt I x₀ x) := by
  rw [form_in_coord_eq_coord_change I φ x (mem_chart_source H x),
      formCoordChange_self I k (achart H x) x
        (by rw [tangentBundleCore_baseSet]; exact mem_chart_source H x) (φ x),
      ← form_in_coord_eq_coord_change I φ x₀ hx]

section BdryManifold

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- The trivialization read of `pullbackBdryFun` at `p₀` equals the `formCoordChange` on `∂M`,
mirroring the analogous identity for `mextDerivFun`. -/
theorem pullback_triv_read_coord_change
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ p : Bdry n M) :
    ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
        (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p₀)
        ⟨p, pullbackBdryFun φ p⟩).2
      = formCoordChange (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) n
          (achart (EuclideanSpace ℝ (Fin n)) p)
          (achart (EuclideanSpace ℝ (Fin n)) p₀) p
          (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
            (formInCoord (𝓡∂ (n + 1)) φ p.val
              (extChartAt (𝓡∂ (n + 1)) p.val p.val))) := by
  simp only [pullbackBdryFun]
  have hmem : p ∈ (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p).baseSet :=
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).mem_localTrivAt_baseSet p
  have hfun : (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p).symmL ℝ p =
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).coordChange
        ((formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).indexAt p)
        ((formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).indexAt p) p :=
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
      (M := Bdry n M) n).trivializationAt_symmL hmem
  rw [hfun]
  have step1 : ∀ (z : (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
        (M := Bdry n M) n).Fiber p),
      ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p₀)
          ⟨p, z⟩).2 =
        formCoordChange (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) n
          (achart (EuclideanSpace ℝ (Fin n)) p)
          (achart (EuclideanSpace ℝ (Fin n)) p₀) p z :=
    fun _ ↦ rfl
  rw [step1]
  have hself :=
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).coordChange_self
      ((formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).indexAt p) p
      ((formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).mem_baseSet_at p)
      (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
        (formInCoord (𝓡∂ (n + 1)) φ p.val (extChartAt (𝓡∂ (n + 1)) p.val p.val)))
  exact congrArg
    (formCoordChange (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) n
      (achart (EuclideanSpace ℝ (Fin n)) p) (achart (EuclideanSpace ℝ (Fin n)) p₀) p)
    hself

/-- The composition `extChartAt p₀.val ∘ val` is smooth on the preimage of the chart source,
via `ContMDiffOn.comp` applied to `contMDiffOn_extChartAt` and `hval`. -/
theorem extchart_comp_val_contmdiffon (p₀ : Bdry n M)
    (hval : ContMDiff 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (𝓡∂ (n + 1)) ∞
      (fun p : Bdry n M => p.val)) :
    ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin n))
      𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1))) ∞
      (fun p : Bdry n M => extChartAt (𝓡∂ (n + 1)) p₀.val p.val)
      ((fun p : Bdry n M => p.val) ⁻¹'
        (chartAt (EuclideanHalfSpace (n + 1)) p₀.val).source) := by
  apply ContMDiffOn.comp (contMDiffOn_extChartAt (I := 𝓡∂ (n + 1)) (x := p₀.val))
    hval.contMDiffOn
  intro p hp
  exact hp

/-- CLM post-composition by `compContinuousLinearMapCLM faceEmbedL` preserves `ContMDiffOn`
on the chart target: reduce to `ContDiffOn` and apply `continuousLinearMap_comp`. -/
theorem pullback_coord_rep_contmdiffon_target
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) :
    ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1)))
      𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) ∞
      (fun y => ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
        (formInCoord (𝓡∂ (n + 1)) φ p₀.val y))
      (extChartAt (𝓡∂ (n + 1)) p₀.val).target := by
  have hsmooth := form_in_coord_smooth (𝓡∂ (n + 1)) φ p₀.val
  rw [contMDiffOn_iff_contDiffOn]
  exact hsmooth.continuousLinearMap_comp
    (ContinuousAlternatingMap.compContinuousLinearMapCLM (𝕜 := ℝ) faceEmbedL)

/-- The preimage of the chart source under `val` is a neighbourhood of `p₀` in `Bdry n M`,
since `val` is continuous and the chart source is open. -/
theorem val_preimage_chart_source_mem_nhds (p₀ : Bdry n M)
    (hval : ContMDiff 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (𝓡∂ (n + 1)) ∞
      (fun p : Bdry n M => p.val)) :
    (fun p : Bdry n M => p.val) ⁻¹'
      (chartAt (EuclideanHalfSpace (n + 1)) p₀.val).source ∈ nhds p₀ := by
  apply hval.continuous.continuousAt.preimage_mem_nhds
  exact (chartAt (EuclideanHalfSpace (n + 1)) p₀.val).open_source.mem_nhds
    (mem_chart_source _ _)

/-- The ambient `formCoordChange` on `Bdry n M` commutes with `compContinuousLinearMapCLM
faceEmbedL`: the coordinate change on `∂M` can be moved outside the CLM precomposition.
The CLM identity is obtained by differentiating the face-sandwich identity and applying
`HasFDerivAt.unique`. -/
theorem pullback_coord_change_commute
    (p₀ p : Bdry n M)
    (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source)
    (w : EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ) :
    formCoordChange (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) n
        (achart (EuclideanSpace ℝ (Fin n)) p)
        (achart (EuclideanSpace ℝ (Fin n)) p₀) p
        (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL w)
      = ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
          (formCoordChange (𝓡∂ (n + 1)) n
            (achart (EuclideanHalfSpace (n + 1)) p.val)
            (achart (EuclideanHalfSpace (n + 1)) p₀.val) p.val w) := by
  have hA := extChartAt_trans_comp_faceEmbed_hasFDerivAt p₀ p hp
  have hB := faceEmbed_comp_bdry_trans_hasFDerivAt p₀ p hp
  have hC := extChartAt_trans_faceEmbed_eventuallyEq p₀ p hp
  have hCLM := hA.unique (hB.congr_of_eventuallyEq hC)
  ext m
  simp only [formCoordChange, ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
    ContinuousAlternatingMap.compContinuousLinearMap_apply]
  congr 1
  funext u
  exact (DFunLike.congr_fun hCLM (m u)).symm

/-- The trivialization read of `pullbackBdryFun φ` at a point `p` in the chart source of `p₀`
equals `compContinuousLinearMapCLM faceEmbedL` applied to the coordinate representative of `φ`
at the basepoint `p₀`. Proved by chaining `pullback_triv_read_coord_change`,
`pullback_coord_change_commute`, and `form_coord_change_transport_self`. -/
theorem pullback_triv_read
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ p : Bdry n M)
    (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source) :
    ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
        (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p₀)
        ⟨p, pullbackBdryFun φ p⟩).2
      = ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
          (formInCoord (𝓡∂ (n + 1)) φ p₀.val
            (extChartAt (𝓡∂ (n + 1)) p₀.val p.val)) := by
  have h_val : p.val ∈ (chartAt (EuclideanHalfSpace (n + 1)) p₀.val).source :=
    (Set.mem_of_mem_inter_left hp)
  have h_read : ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
        (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p₀)
        ⟨p, pullbackBdryFun φ p⟩).2
      = formCoordChange (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) n
          (achart (EuclideanSpace ℝ (Fin n)) p)
          (achart (EuclideanSpace ℝ (Fin n)) p₀) p
          (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
            (formInCoord (𝓡∂ (n + 1)) φ p.val
              (extChartAt (𝓡∂ (n + 1)) p.val p.val))) :=
    pullback_triv_read_coord_change φ p₀ p
  have h_comm : formCoordChange (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) n
          (achart (EuclideanSpace ℝ (Fin n)) p)
          (achart (EuclideanSpace ℝ (Fin n)) p₀) p
          (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
            (formInCoord (𝓡∂ (n + 1)) φ p.val
              (extChartAt (𝓡∂ (n + 1)) p.val p.val)))
      = ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
          (formCoordChange (𝓡∂ (n + 1)) n
            (achart (EuclideanHalfSpace (n + 1)) p.val)
            (achart (EuclideanHalfSpace (n + 1)) p₀.val) p.val
            (formInCoord (𝓡∂ (n + 1)) φ p.val
              (extChartAt (𝓡∂ (n + 1)) p.val p.val))) :=
    pullback_coord_change_commute p₀ p hp
      (formInCoord (𝓡∂ (n + 1)) φ p.val (extChartAt (𝓡∂ (n + 1)) p.val p.val))
  have h_transport : formCoordChange (𝓡∂ (n + 1)) n
        (achart (EuclideanHalfSpace (n + 1)) p.val)
        (achart (EuclideanHalfSpace (n + 1)) p₀.val) p.val
        (formInCoord (𝓡∂ (n + 1)) φ p.val (extChartAt (𝓡∂ (n + 1)) p.val p.val))
      = formInCoord (𝓡∂ (n + 1)) φ p₀.val (extChartAt (𝓡∂ (n + 1)) p₀.val p.val) :=
    form_coord_change_transport_self (𝓡∂ (n + 1)) φ p₀.val p.val h_val
  rw [h_read, h_comm, h_transport]

/-- The fixed-basepoint coordinate formula for the pullback section is smooth at `p₀`.
Factor as `(CLM ∘ formInCoord at p₀.val) ∘ (extChartAt p₀.val ∘ val)` and apply
`ContMDiffOn.comp` followed by `ContMDiffOn.contMDiffAt`. -/
theorem pullback_fixed_chart_contmdiff_at
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M)
    (hval : ContMDiff 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (𝓡∂ (n + 1)) ∞
      (fun p : Bdry n M => p.val)) :
    ContMDiffAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n))
      𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) ∞
      (fun p : Bdry n M =>
        ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
          (formInCoord (𝓡∂ (n + 1)) φ p₀.val
            (extChartAt (𝓡∂ (n + 1)) p₀.val p.val))) p₀ := by
  have h_outer : ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1)))
      𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) ∞
      (fun y => ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
        (formInCoord (𝓡∂ (n + 1)) φ p₀.val y))
      (extChartAt (𝓡∂ (n + 1)) p₀.val).target :=
    pullback_coord_rep_contmdiffon_target φ p₀
  have h_inner : ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin n))
      𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1))) ∞
      (fun p : Bdry n M => extChartAt (𝓡∂ (n + 1)) p₀.val p.val)
      ((fun p : Bdry n M => p.val) ⁻¹'
        (chartAt (EuclideanHalfSpace (n + 1)) p₀.val).source) :=
    extchart_comp_val_contmdiffon p₀ hval
  have h_nhds : (fun p : Bdry n M => p.val) ⁻¹'
      (chartAt (EuclideanHalfSpace (n + 1)) p₀.val).source ∈ nhds p₀ :=
    val_preimage_chart_source_mem_nhds p₀ hval
  have h_maps : Set.MapsTo (fun p : Bdry n M => extChartAt (𝓡∂ (n + 1)) p₀.val p.val)
      ((fun p : Bdry n M => p.val) ⁻¹'
        (chartAt (EuclideanHalfSpace (n + 1)) p₀.val).source)
      (extChartAt (𝓡∂ (n + 1)) p₀.val).target := by
    intro p hp
    exact (extChartAt (𝓡∂ (n + 1)) p₀.val).map_source (by simpa [extChartAt_source] using hp)
  exact (h_outer.comp h_inner h_maps).contMDiffAt h_nhds

/-- The pullback of a smooth `n`-form `φ` on `M` along the boundary inclusion is a smooth
section of the `n`-form bundle over `Bdry n M`. At each point, smoothness of the trivialization
read follows from `pullback_fixed_chart_contmdiff_at`; `pullback_triv_read` identifies the
trivialization with the fixed-chart formula near the basepoint. -/
theorem contMDiff_pullbackBdryFun (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    ContMDiff (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
        ((𝓘(ℝ, EuclideanSpace ℝ (Fin n))).prod
          𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)) ∞
      (fun p => Bundle.TotalSpace.mk'
        (E := fun q =>
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber q)
        (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) p (pullbackBdryFun φ p)) := by
  intro p₀
  have hp₀ : p₀ ∈ (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p₀).baseSet :=
    FiberBundle.mem_baseSet_trivializationAt' p₀
  rw [Bundle.Trivialization.contMDiffAt_section_iff _ hp₀]
  have h_val : ContMDiff 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (𝓡∂ (n + 1)) ∞
      (fun p : Bdry n M => p.val) := bdry_val_contmdiff
  have h_smooth : ContMDiffAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n))
      𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) ∞
      (fun p : Bdry n M =>
        ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
          (formInCoord (𝓡∂ (n + 1)) φ p₀.val
            (extChartAt (𝓡∂ (n + 1)) p₀.val p.val))) p₀ :=
    pullback_fixed_chart_contmdiff_at φ p₀ h_val
  refine h_smooth.congr_of_eventuallyEq ?_
  filter_upwards [(chartAt (EuclideanSpace ℝ (Fin n)) p₀).open_source.mem_nhds
    (mem_chart_source (EuclideanSpace ℝ (Fin n)) p₀)] with p hp
  exact pullback_triv_read φ p₀ p hp

end BdryManifold

end Library.Geometry.ManifoldBdry.PullbackFormContMDiff
