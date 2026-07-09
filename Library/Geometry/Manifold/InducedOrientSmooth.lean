import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.InducedOrientDefs
import Library.Geometry.Manifold.MExtDerivCoord         -- formInCoord, instFormBundleContMDiff
import Library.Geometry.Manifold.StokesIntegralDefs      -- OrientedManifold (+ refForm)
import Library.Geometry.ManifoldBdry.BdryIsManifold      -- isManifold_bdry (instance), instBdryChartedSpace
import Library.Geometry.ManifoldBdry.PullbackBdryDefs    -- faceEmbedL
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff
import Library.Geometry.ManifoldBoundary.CompactBdry     -- Bdry
import Mathlib.Algebra.Module.Basic
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.PartitionOfUnity
import Mathlib.Geometry.Manifold.VectorBundle.Basic
import Mathlib.Geometry.Manifold.VectorBundle.SmoothSection
import Mathlib.Topology.Algebra.Module.Alternating.Basic
import Mathlib.Topology.FiberBundle.Basic
import Mathlib.Topology.FiberBundle.Trivialization
import Mathlib.Topology.LocallyFinite
import Mathlib.Topology.VectorBundle.Basic

/-! # Smoothness of the induced orientation section

This file proves that `inducedOrientFun`, the canonical section of the orientation bundle on
the boundary of an oriented manifold with corners, is globally smooth (`ContMDiff`).

## Main statements

- `chartfun_outer_contmdiffon`: the fixed-chart orientation formula is `ContMDiffOn` on the
  extended chart target.
- `chartfun_triv_read`: the trivialization readout of `inducedOrientChartFun` collapses to the
  raw fixed-chart formula on the chart source.
- `chartfun_formula_contmdiffon`: the fixed-chart formula is `ContMDiffOn` on the chart source.
- `chartfun_section_contmdiffon_source`: the candidate section is `ContMDiffOn` on the chart
  source, combining the two results above.
- `summand_section_contmdiff`: each POU-weighted summand is globally smooth.
- `summand_support_locally_finite`: the summand supports form a locally finite family.
- `contMDiff_inducedOrientFun`: `inducedOrientFun` is a globally smooth section.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.InducedOrientDefs
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.BdryValSmooth
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.InducedOrientSmooth

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M]

/-- The fixed-chart formula for the induced orientation is `ContMDiffOn` on the extended chart
target. Both models are vector spaces, so `contMDiffOn_iff_contDiffOn` reduces smoothness to
`ContDiffOn`; the map is the fixed CLM `compCLM faceEmbedL ∘ curryLeft(-e₀)` composed with
`formInCoord refForm q.val`, which is `ContDiffOn` by `form_in_coord_smooth`. -/
theorem chartfun_outer_contmdiffon (q : Bdry n M) :
    ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1)))
      𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) ∞
      (fun y => ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
        ((formInCoord (𝓡∂ (n + 1)) (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
            q.val y).curryLeft
          (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))
      (extChartAt (𝓡∂ (n + 1)) q.val).target := by
  rw [contMDiffOn_iff_contDiffOn]
  have hsmooth : ContDiffOn ℝ ∞
      (formInCoord (𝓡∂ (n + 1)) (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) q.val)
      (extChartAt (𝓡∂ (n + 1)) q.val).target :=
    form_in_coord_smooth _ _ _
  let outerCLM : (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin (n + 1)]→L[ℝ] ℝ) →L[ℝ]
      (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) :=
    (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL).comp
      ((ContinuousLinearMap.apply ℝ _ (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)).comp
        ContinuousAlternatingMap.curryLeftLI.toContinuousLinearMap)
  exact (outerCLM.contDiff.contDiffOn.comp hsmooth (Set.mapsTo_univ _ _)).congr
    (fun _ _ ↦ rfl)

/-- On the chart source of `q`, the second component of the trivialization of
`inducedOrientChartFun q` at a point `p` equals the raw fixed-chart formula. The
trivialization's `symmL` wrapper cancels via `continuousLinearMapAt_symmL`. -/
theorem chartfun_triv_read (q p : Bdry n M)
    (hp : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    ((trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
        (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber q)
        ⟨p, inducedOrientChartFun q p⟩).2
      = ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
          ((formInCoord (𝓡∂ (n + 1)) (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
              q.val (extChartAt (𝓡∂ (n + 1)) q.val p.val)).curryLeft
            (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)) := by
  simp only [inducedOrientChartFun]
  have h_base : (chartAt (EuclideanSpace ℝ (Fin n)) q).source ⊆
      (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
        (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber q).baseSet :=
    subset_rfl
  exact (Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ (h_base hp) _).symm.trans
    (Trivialization.continuousLinearMapAt_symmL _ (h_base hp) _)

/-- The fixed-chart formula for the induced orientation is `ContMDiffOn` on the chart source
of `q`, obtained by composing `chartfun_outer_contmdiffon` with the smooth map
`p ↦ extChartAt (𝓡∂ (n + 1)) q.val p.val`. -/
theorem chartfun_formula_contmdiffon (q : Bdry n M) :
    ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin n))
      𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) ∞
      (fun p : Bdry n M =>
        ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
          ((formInCoord (𝓡∂ (n + 1)) (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
              q.val (extChartAt (𝓡∂ (n + 1)) q.val p.val)).curryLeft
            (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))
      (chartAt (EuclideanSpace ℝ (Fin n)) q).source := by
  have h_outer : ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1)))
      𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) ∞
      (fun y => ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
        ((formInCoord (𝓡∂ (n + 1)) (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
            q.val y).curryLeft
          (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))
      (extChartAt (𝓡∂ (n + 1)) q.val).target := chartfun_outer_contmdiffon q
  have h_subset : (chartAt (EuclideanSpace ℝ (Fin n)) q).source ⊆
      (fun p : Bdry n M => p.val) ⁻¹'
        (chartAt (EuclideanHalfSpace (n + 1)) q.val).source :=
    fun p hp ↦ Set.mem_of_mem_inter_left hp
  have h_inner : ContMDiffOn 𝓘(ℝ, EuclideanSpace ℝ (Fin n))
      𝓘(ℝ, EuclideanSpace ℝ (Fin (n + 1))) ∞
      (fun p : Bdry n M => extChartAt (𝓡∂ (n + 1)) q.val p.val)
      (chartAt (EuclideanSpace ℝ (Fin n)) q).source :=
    (extchart_comp_val_contmdiffon q bdry_val_contmdiff).mono h_subset
  have h_maps : Set.MapsTo (fun p : Bdry n M => extChartAt (𝓡∂ (n + 1)) q.val p.val)
      (chartAt (EuclideanSpace ℝ (Fin n)) q).source
      (extChartAt (𝓡∂ (n + 1)) q.val).target :=
    fun p hp ↦ (extChartAt (𝓡∂ (n + 1)) q.val).map_source
      (by simpa [extChartAt_source] using h_subset hp)
  exact h_outer.comp h_inner h_maps

/-- The section `p ↦ ⟨p, inducedOrientChartFun q p⟩` of the orientation bundle is
`ContMDiffOn` on the chart source of `q`. The trivialization side condition is discharged by
`subset_rfl`; `chartfun_triv_read` shows the trivialization readout equals the formula proven
smooth by `chartfun_formula_contmdiffon`, and the two are combined via `ContMDiffOn.congr`. -/
theorem chartfun_section_contmdiffon_source (q : Bdry n M) :
    ContMDiffOn (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
      ((𝓘(ℝ, EuclideanSpace ℝ (Fin n))).prod
        𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)) ∞
      (fun p => Bundle.TotalSpace.mk'
        (E := fun x =>
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber x)
        (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) p (inducedOrientChartFun q p))
      (chartAt (EuclideanSpace ℝ (Fin n)) q).source := by
  rw [Trivialization.contMDiffOn_section_iff
    (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber q)
    (chartAt (EuclideanSpace ℝ (Fin n)) q).open_source subset_rfl]
  exact (chartfun_formula_contmdiffon q).congr (fun p hp ↦ chartfun_triv_read q p hp)

section T2SigmaCompact

variable [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)]

/-- Given that the fixed-chart candidate section is `ContMDiffOn` on the chart source of `q`,
the POU-weighted summand `p ↦ ⟨p, inducedOrientPOU n M q p • inducedOrientChartFun q p⟩` is
globally smooth. This follows from `ContMDiffOn.smul_section_of_tsupport`, using the fact that
the partition of unity is subordinate to the chart source. -/
theorem summand_section_contmdiff (q : Bdry n M)
    (h_cand : ContMDiffOn (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
      ((𝓘(ℝ, EuclideanSpace ℝ (Fin n))).prod
        𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)) ∞
      (fun p => Bundle.TotalSpace.mk'
        (E := fun x =>
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber x)
        (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) p (inducedOrientChartFun q p))
      (chartAt (EuclideanSpace ℝ (Fin n)) q).source) :
    ContMDiff (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
      ((𝓘(ℝ, EuclideanSpace ℝ (Fin n))).prod
        𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)) ∞
      (fun p => Bundle.TotalSpace.mk'
        (E := fun x =>
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber x)
        (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) p
      (inducedOrientPOU n M q p • inducedOrientChartFun q p)) := by
  refine ContMDiffOn.smul_section_of_tsupport
    (u := (chartAt (EuclideanSpace ℝ (Fin n)) q).source)
    ?_ (chartAt (EuclideanSpace ℝ (Fin n)) q).open_source ?_ h_cand
  · exact (inducedOrientPOU n M q).contMDiff.contMDiffOn
  · exact (SmoothPartitionOfUnity.exists_isSubordinate_chartAt_source
      (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M)).choose_spec q

/-- The supports of the POU-weighted summands form a locally finite family. The support of
`q ↦ inducedOrientPOU n M q p • inducedOrientChartFun q p` is contained in the support of
`inducedOrientPOU n M q` via `Function.support_smul_subset_left`, and the POU's own supports
are locally finite. -/
theorem summand_support_locally_finite :
    LocallyFinite fun q : Bdry n M =>
      {p : Bdry n M | inducedOrientPOU n M q p • inducedOrientChartFun q p ≠ 0} := by
  apply (inducedOrientPOU n M).locallyFinite.subset
  intro q p hp
  exact Function.support_smul_subset_left _ _ hp

/-- `inducedOrientFun` is a globally smooth section of the orientation bundle on `Bdry n M`.
The proof applies `ContMDiff.finsum_section_of_locallyFinite` to the POU-weighted family, using
local smoothness on each chart source (`chartfun_section_contmdiffon_source` upgraded via
`summand_section_contmdiff`) and local finiteness of the summand supports
(`summand_support_locally_finite`). -/
theorem contMDiff_inducedOrientFun :
    ContMDiff (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
        ((𝓘(ℝ, EuclideanSpace ℝ (Fin n))).prod
          𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)) ∞
      (fun p => Bundle.TotalSpace.mk'
        (E := fun q =>
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber q)
        (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) p (inducedOrientFun p)) := by
  have h_lf : LocallyFinite fun q : Bdry n M =>
      {p : Bdry n M | inducedOrientPOU n M q p • inducedOrientChartFun q p ≠ 0} :=
    summand_support_locally_finite
  have h_cand : ∀ q : Bdry n M,
      ContMDiffOn (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
        ((𝓘(ℝ, EuclideanSpace ℝ (Fin n))).prod
          𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)) ∞
        (fun p => Bundle.TotalSpace.mk'
          (E := fun x =>
            (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber x)
          (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) p (inducedOrientChartFun q p))
        (chartAt (EuclideanSpace ℝ (Fin n)) q).source :=
    fun q => chartfun_section_contmdiffon_source q
  have h_summand : ∀ q : Bdry n M,
      ContMDiff (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
        ((𝓘(ℝ, EuclideanSpace ℝ (Fin n))).prod
          𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)) ∞
        (fun p => Bundle.TotalSpace.mk'
          (E := fun x =>
            (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber x)
          (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) p
          (inducedOrientPOU n M q p • inducedOrientChartFun q p)) :=
    fun q => summand_section_contmdiff q (h_cand q)
  exact ContMDiff.finsum_section_of_locallyFinite h_lf h_summand

end T2SigmaCompact

end Library.Geometry.Manifold.InducedOrientSmooth
