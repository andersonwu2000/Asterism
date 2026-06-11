/-
  Defs.lean — PARKED (not yet buildable). Owns `bdryChart`, the boundary chart as
  an `OpenPartialHomeomorph`, assembled from the cited chart DATA + the partial-equiv
  laws (`Library…BoundaryChart`) + the topological laws (P7c, `stokes_bdry_chart_topo`).

  ⚠️ FINALIZE AFTER P7c MIGRATES: the import + names of the four topological laws
  (`chart_source_is_open` / `chart_target_is_open` / `chart_to_fun_continuous_on` /
  `chart_inv_fun_continuous_on`) are TBD — P7c's migrate STALLED (librarian gap), its
  Library module/path is not final (it tried `Library/Geometry/ManifoldBdry/FaceMap`).
  Update the `import`/open and possibly lambda-wrap the strict-implicit chart fields.
-/
import Mathlib
import Library.Geometry.ManifoldBoundary.Defs          -- chart data
import Library.Geometry.ManifoldBoundary.BoundaryChart  -- chart_map_source/_target/left/right_inv
import Library.Geometry.ManifoldBdry.BdryChart          -- P7c: isOpen_* / continuousOn_*

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.BoundaryChart
open Library.Geometry.ManifoldBdry.BdryChart

namespace Problems.Geometry.stokes_bdry_chartedspace

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- The boundary chart at `p` as an `OpenPartialHomeomorph`, the chart type a
    `ChartedSpace` consumes. All fields are cited proven facts (no `sorry`):
    partial-equiv laws from `BoundaryChart`, topological laws from P7c. -/
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

end Problems.Geometry.stokes_bdry_chartedspace
