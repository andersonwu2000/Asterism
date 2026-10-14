/-
  Defs.lean — PARKED (not yet buildable). Owns `bdryChart`, the boundary chart as
  an `OpenPartialHomeomorph`, assembled from the cited chart DATA + the partial-equiv
  laws (`Problems.Geometry.stokes_bdry_chart`) + the topological laws (P7c, `stokes_bdry_chart_topo`).

  ⚠️ FINALIZE AFTER P7c MIGRATES: the import + names of the four topological laws
  (`chart_source_is_open` / `chart_target_is_open` / `chart_to_fun_continuous_on` /
  `chart_inv_fun_continuous_on`) are TBD — P7c's migrate STALLED (librarian gap), its
  Library module/path is not final (it tried `Library/Geometry/ManifoldBdry/FaceMap`).
  Update the `import`/open and possibly lambda-wrap the strict-implicit chart fields.
-/
import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs.L_chart_left_inv
import Problems.Geometry.stokes_bdry_chart.proofs.L_chart_map_source
import Problems.Geometry.stokes_bdry_chart.proofs.L_chart_map_target
import Problems.Geometry.stokes_bdry_chart.proofs.L_chart_right_inv
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_inv_fun_continuous_on
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_source_is_open
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_is_open
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_to_fun_continuous_on
import Problems.Geometry.stokes_bdry_compact.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Problems.Geometry.stokes_bdry_compact (Bdry)
open Problems.Geometry.stokes_bdry_chart (chartInvFun chartSource chartTarget chartToFun chart_left_inv chart_map_source chart_map_target chart_right_inv)

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
  open_source := Problems.Geometry.stokes_bdry_chart_topo.chart_source_is_open p
  open_target := Problems.Geometry.stokes_bdry_chart_topo.chart_target_is_open p
  continuousOn_toFun := Problems.Geometry.stokes_bdry_chart_topo.chart_to_fun_continuous_on p
  continuousOn_invFun := Problems.Geometry.stokes_bdry_chart_topo.chart_inv_fun_continuous_on p

end Problems.Geometry.stokes_bdry_chartedspace
