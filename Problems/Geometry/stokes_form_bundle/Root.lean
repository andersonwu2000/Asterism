-- main: formBundleCore has C^∞ transition functions — compose the C^∞ brick
-- `compContinuousLinearMapCLM` (s11679) with the C^∞ tangent coord-change.
import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_bundle.proofs._strategy_s11679

open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange

namespace Problems.Geometry.stokes_form_bundle

theorem main : ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H] (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    (k : ℕ),
    (formBundleCore (M := M) I k).IsContMDiff I ∞ := by
  intro E _ _ H _ I M _ _ hM k
  refine ⟨fun i j ↦ ?_⟩
  have hm : IsManifold I (∞ + 1) M := hM
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
    s11679 (F := E) (G := ℝ) (ι := Fin k)
  change ContMDiffOn I 𝓘(ℝ, E [⋀^Fin k]→L[ℝ] ℝ →L[ℝ] E [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun x ↦ ContinuousAlternatingMap.compContinuousLinearMapCLM
        ((tangentBundleCore I M).coordChange j i x))
      ((tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j)
  exact hsmooth.contMDiff.comp_contMDiffOn hcoord'

end Problems.Geometry.stokes_form_bundle
