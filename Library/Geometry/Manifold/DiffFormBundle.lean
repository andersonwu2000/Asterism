import Library.Geometry.Manifold.AlternatingMapContDiff
import Library.Geometry.Manifold.FormCoordChange       -- formCoordChange (def), formCoordChange_comp
import Library.Geometry.Manifold.FormCoordChangeCont    -- continuousOn_formCoordChange
import Library.Geometry.Manifold.FormCoordChangeSelf    -- formCoordChange_self
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.ContMDiff.NormedSpace
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.VectorBundle.Basic
import Mathlib.Geometry.Manifold.VectorBundle.SmoothSection
import Mathlib.Geometry.Manifold.VectorBundle.Tangent
import Mathlib.Topology.Algebra.Module.Alternating.Topology
import Mathlib.Topology.VectorBundle.Basic

/-!
# Differential Form Bundle

Constructs the vector-bundle structure on the bundle `⋀ᵏ T*M` of alternating `k`-forms
on a smooth manifold `M`, and verifies that the coordinate changes are smooth.

## Main definitions

- `formBundleCore`: the `VectorBundleCore` whose fibers are `E [⋀^Fin k]→L[ℝ] ℝ`.
- `DiffForm`: the type of smooth (`C^∞`) differential `k`-forms on `M`.
- `instFormFiberBundle`, `instFormVectorBundle`: bundle instances for `⋀ᵏ T*M`.

## Main statements

- `formBundleCore_isContMDiff`: the coordinate changes of `formBundleCore` are `C^∞`.
-/

open Bundle
open Library.Geometry.Manifold.AlternatingMapContDiff
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeCont
open Library.Geometry.Manifold.FormCoordChangeSelf
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.DiffFormBundle

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- The `VectorBundleCore` for the bundle of alternating `k`-forms on `M`.
The base sets and coordinate changes are inherited from the tangent bundle core. -/
noncomputable def formBundleCore (k : ℕ) :
    VectorBundleCore ℝ M (E [⋀^Fin k]→L[ℝ] ℝ) (atlas H M) where
  baseSet i := (tangentBundleCore I M).baseSet i
  isOpen_baseSet i := (tangentBundleCore I M).isOpen_baseSet i
  indexAt := (tangentBundleCore I M).indexAt
  mem_baseSet_at := (tangentBundleCore I M).mem_baseSet_at
  coordChange := formCoordChange I k
  coordChange_self := formCoordChange_self I k
  continuousOn_coordChange := continuousOn_formCoordChange I k
  coordChange_comp := formCoordChange_comp I k

/-- A smooth differential `k`-form on `M`: a smooth section of the bundle `⋀ᵏ T*M`.
`I` and `M` are explicit arguments following the mathlib convention for section type-formers. -/
abbrev DiffForm (I : ModelWithCorners ℝ E H) (M : Type*) [TopologicalSpace M]
    [ChartedSpace H M] [IsManifold I ∞ M] (k : ℕ) : Type _ :=
  Cₛ^∞⟮I; (E [⋀^Fin k]→L[ℝ] ℝ), (formBundleCore (M := M) I k).Fiber⟯

/-- `⋀ᵏ T*M` has a natural fiber-bundle structure. -/
noncomputable instance instFormFiberBundle (k : ℕ) :
    FiberBundle (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber :=
  (formBundleCore (M := M) I k).fiberBundle

/-- `⋀ᵏ T*M` has a natural vector-bundle structure over `ℝ`. -/
noncomputable instance instFormVectorBundle (k : ℕ) :
    VectorBundle ℝ (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber :=
  (formBundleCore (M := M) I k).vectorBundle

/-- The coordinate changes of the differential form bundle core are smooth (`C^∞`). -/
theorem formBundleCore_isContMDiff (k : ℕ) : (formBundleCore (M := M) I k).IsContMDiff I ∞ := by
  refine ⟨fun i j ↦ ?_⟩
  have hm : IsManifold I (∞ + 1) M := ‹IsManifold I ∞ M›
  have htcm : (tangentBundleCore I M).IsContMDiff I ∞ :=
    tangentBundleCore.isContMDiff (h := hm)
  have hcoord : ContMDiffOn I 𝓘(ℝ, E →L[ℝ] E) ∞
      ((tangentBundleCore I M).coordChange j i)
      ((tangentBundleCore I M).baseSet j ∩ (tangentBundleCore I M).baseSet i) :=
    htcm.contMDiffOn_coordChange j i
  have hcoord' : ContMDiffOn I 𝓘(ℝ, E →L[ℝ] E) ∞
      ((tangentBundleCore I M).coordChange j i)
      ((tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j) :=
    hcoord.mono (Set.inter_comm _ _).subset
  have hsmooth : ContDiff ℝ ∞ (fun g : E →L[ℝ] E ↦
      (ContinuousAlternatingMap.compContinuousLinearMapCLM g :
        (E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ] (E [⋀^Fin k]→L[ℝ] ℝ))) :=
    contdiff_comp_continuous_linear_map_clm (F := E) (G := ℝ) (ι := Fin k)
  change ContMDiffOn I 𝓘(ℝ, E [⋀^Fin k]→L[ℝ] ℝ →L[ℝ] E [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun x ↦ ContinuousAlternatingMap.compContinuousLinearMapCLM
        ((tangentBundleCore I M).coordChange j i x))
      ((tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j)
  exact hsmooth.contMDiff.comp_contMDiffOn hcoord'

end Library.Geometry.Manifold.DiffFormBundle
