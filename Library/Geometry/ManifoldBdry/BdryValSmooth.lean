import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.MExtDerivCoord         -- formInCoord, instFormBundleContMDiff
import Library.Geometry.ManifoldBdry.BdryIsManifold      -- instBdryChartedSpace, isManifold_bdry
import Library.Geometry.ManifoldBoundary.CompactBdry     -- Bdry, TopologicalSpace
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.Set.Basic
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.Notation
import Mathlib.Order.Filter.Basic
import Mathlib.Topology.Constructions
import Mathlib.Topology.NhdsWithin

/-!
# Smoothness of the boundary inclusion

The boundary `Bdry n M` of an `(n+1)`-dimensional manifold with boundary `M` carries a natural
manifold structure. This file establishes that the inclusion map `Bdry n M → M` is smooth.

## Main statements

- `bdry_val_contmdiff`: the inclusion `fun p : Bdry n M ↦ p.val` is `ContMDiff ∞`.
- `bdry_val_rep_eq_faceembed`: the chart representation of the inclusion equals `faceEmbed`.
- `bdry_val_chartrep_contdiffwithinat`: the chart representation is `ContDiffWithinAt ∞`.
- `bdry_extchart_self_mem_charttarget`: the self-image of the boundary chart lies in `chartTarget`.
- `(Set.mem_of_mem_inter_left in) the boundary chart source implies membership in
  the ambient chart source.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.ManifoldBdry.BdryChart
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.ChartedBdry
open Library.Geometry.ManifoldBdry.SmoothFaceMaps
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.BdryValSmooth

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- The chart representation of the boundary inclusion equals `faceEmbed`.

On `chartTarget p`, the map
`extChartAt (𝓡∂ (n+1)) p.val ∘ (·.val) ∘ (extChartAt 𝓘 p).symm` agrees with `faceEmbed`. -/
theorem bdry_val_rep_eq_faceembed (p : Bdry n M) : ∀ z ∈ chartTarget p,
    extChartAt (𝓡∂ (n + 1)) p.val
      ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p).symm z).val = faceEmbed z := by
  intro z hz
  have hmem : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    have hz' := hz
    rw [chartTarget_eq_faceEmbed_preimage p] at hz'
    exact hz'
  have h1 := chartInvFun_val_eq_extChartAt_symm_faceEmbed p z hz
  have heq : (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p).symm z = chartInvFun p z := by
    simp only [extChartAt, OpenPartialHomeomorph.extend_coe_symm,
               modelWithCornersSelf_coe_symm, Function.comp_id]
    rfl
  have h2 : ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p).symm z).val =
      (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z) := by
    rw [heq]; exact h1
  rw [h2]
  exact (extChartAt (𝓡∂ (n + 1)) p.val).right_inv hmem

/-- The chart representation of the boundary inclusion is `ContDiffWithinAt ∞` at a basepoint,
given that the representation agrees with `faceEmbed` on `chartTarget p`. -/
theorem bdry_val_chartrep_contdiffwithinat (p : Bdry n M)
    (h_rep : ∀ z ∈ chartTarget p,
      extChartAt (𝓡∂ (n + 1)) p.val
        ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p).symm z).val = faceEmbed z)
    (h_mem : extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p p ∈ chartTarget p) :
    ContDiffWithinAt ℝ ∞
      ((extChartAt (𝓡∂ (n + 1)) p.val) ∘ (fun q : Bdry n M ↦ q.val) ∘
        (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p).symm)
      (Set.range 𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
      (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p p) := by
  apply (contDiff_faceEmbed.contDiffWithinAt.mono (Set.subset_univ _)).congr_of_eventuallyEq
  · apply Filter.Eventually.filter_mono nhdsWithin_le_nhds
    exact ((isOpen_chartTarget p).eventually_mem h_mem).mono fun z hz ↦ by
      simp only [Function.comp]
      exact h_rep z hz
  · simp only [Function.comp]
    exact h_rep _ h_mem

/-- The self-image of the boundary chart at `p` lies in `chartTarget p`. -/
theorem bdry_extchart_self_mem_charttarget (p : Bdry n M) :
    extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p p ∈ chartTarget p := by
  have hmem := mem_extChartAt_target (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p
  rwa [extChartAt_target (𝓘(ℝ, EuclideanSpace ℝ (Fin n))), modelWithCornersSelf_coe_symm,
    Set.preimage_id, modelWithCornersSelf_coe, Set.range_id, Set.inter_univ] at hmem

/-- The inclusion `Bdry n M → M` is smooth. -/
theorem bdry_val_contmdiff :
    ContMDiff 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (𝓡∂ (n + 1)) ∞
      (fun p : Bdry n M ↦ p.val) := by
  intro p
  rw [contMDiffAt_iff]
  refine ⟨continuous_subtype_val.continuousAt, ?_⟩
  have h_rep := bdry_val_rep_eq_faceembed p
  have h_mem := bdry_extchart_self_mem_charttarget p
  exact bdry_val_chartrep_contdiffwithinat p h_rep h_mem

end Library.Geometry.ManifoldBdry.BdryValSmooth
