import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_continuous_face_proj

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

-- chart_to_fun_continuous_on: ContinuousOn (chartToFun p) (chartSource p) by composing
-- faceProj ∘ extChartAt ∘ Subtype.val using continuous_face_proj and continuousOn_extChartAt.
theorem chart_to_fun_continuous_on {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M) : ContinuousOn (chartToFun p) (chartSource p) := by
  change ContinuousOn (fun q : Bdry n M => faceProj (extChartAt (𝓡∂ (n + 1)) p.val q.val))
      (Subtype.val ⁻¹' (extChartAt (𝓡∂ (n + 1)) p.val).source)
  apply Continuous.comp_continuousOn continuous_face_proj
  apply ContinuousOn.comp (continuousOn_extChartAt (I := 𝓡∂ (n + 1)) p.val)
    (continuous_subtype_val.continuousOn
      (s := Subtype.val ⁻¹' (extChartAt (𝓡∂ (n + 1)) p.val).source))
  intro _ hq; exact hq


end Problems.Geometry.stokes_bdry_chart_topo
