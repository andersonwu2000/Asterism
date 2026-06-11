import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

-- faceEmbed is a finite sum of coordinate-projection-scaled constants;
-- continuity follows from continuous_finsetSum + proj continuity + smul.
theorem s11675 {n : ℕ} :
    Continuous (faceEmbed : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin (n + 1)))  := by
  unfold Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed
  refine continuous_finsetSum _ fun i _ => Continuous.smul ?_ continuous_const
  exact (EuclideanSpace.proj (𝕜 := ℝ) i).continuous

end Problems.Geometry.stokes_bdry_chart_topo
