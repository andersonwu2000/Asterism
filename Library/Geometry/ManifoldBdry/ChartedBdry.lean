import Library.Geometry.ManifoldBdry.BdryChart
import Library.Geometry.ManifoldBoundary.BoundaryChart
import Library.Geometry.ManifoldBoundary.Defs
import Mathlib.Analysis.Calculus.ContDiff.FTaylorSeries
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.Bundle
import Mathlib.Data.Set.Operations
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.Notation
import Mathlib.Topology.OpenPartialHomeomorph.Defs

/-!
# Charted-space structure on the boundary

This file constructs the chart data for the boundary `Bdry n M` of an `(n+1)`-dimensional
manifold with boundary.  For each point `p` on the boundary, `bdryChart p` packages the
partial-equivalence laws from `BoundaryChart` and the topological properties (openness,
continuity) from `BdryChart` into a single `OpenPartialHomeomorph` suitable for the
`ChartedSpace` machinery.

## Main definitions

- `bdryChart`: the boundary chart at `p` as an `OpenPartialHomeomorph`.

## Main statements

- `mem_bdryChart_source`: every boundary point belongs to its own chart's source.
-/

open Bundle
open Library.Geometry.ManifoldBdry.BdryChart
open Library.Geometry.ManifoldBoundary.BoundaryChart
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.ChartedBdry

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- The boundary chart at `p` as an `OpenPartialHomeomorph`.  The partial-equiv laws are
supplied by `BoundaryChart` and the topological properties (open source/target, continuity
of both directions) are supplied by `BdryChart`. -/
noncomputable def bdryChart (p : Bdry n M) :
    OpenPartialHomeomorph (Bdry n M) (EuclideanSpace ℝ (Fin n)) where
  toFun := chartToFun p
  invFun := chartInvFun p
  source := chartSource p
  target := chartTarget p
  map_source' := chart_map_source p
  map_target' := chart_map_target p
  left_inv' := chart_left_inv p
  right_inv' := chart_right_inv p
  open_source := isOpen_chartSource p
  open_target := isOpen_chartTarget p
  continuousOn_toFun := continuousOn_chartToFun p
  continuousOn_invFun := continuousOn_chartInvFun p

/-- Every boundary point belongs to the source of its own boundary chart. -/
theorem mem_bdryChart_source (p : Bdry n M) : p ∈ (bdryChart p).source := by
  simp only [bdryChart, chartSource, Set.mem_preimage]
  exact mem_extChartAt_source p.val

end Library.Geometry.ManifoldBdry.ChartedBdry
