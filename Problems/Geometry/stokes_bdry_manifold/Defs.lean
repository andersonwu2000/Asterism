/-
  Defs.lean — PARKED (not yet buildable). Owns the boundary `ChartedSpace` instance,
  built from `bdryChart` + `mem_chart_source` (both cited from P8,
  `stokes_bdry_chartedspace`). The Root proves `∂M` is a `C^∞` manifold.

  ⚠️ FINALIZE AFTER P8 MIGRATES: the import + names of `bdryChart` and the
  `mem_chart_source` lemma are TBD (P8 not yet run). Update `import`/open + the
  `mem_chart_source` field's cited lemma name.
-/
import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_inv_fun_val_eq_symm_face_embed
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_eq_face_embed_preimage
import Problems.Geometry.stokes_bdry_chartedspace.Defs
import Problems.Geometry.stokes_bdry_chartedspace.Root
import Problems.Geometry.stokes_bdry_compact.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Problems.Geometry.stokes_bdry_compact (Bdry)
open Problems.Geometry.stokes_bdry_chartedspace (bdryChart)

namespace Problems.Geometry.stokes_bdry_manifold

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- `∂M` is a charted space over `EuclideanSpace ℝ (Fin n)`: the atlas is the range
    of `bdryChart`, each point charted by `bdryChart`; `mem_chart_source` is P8's
    proven lemma, `chart_mem_atlas` is immediate. -/
noncomputable instance instBdryChartedSpace :
    ChartedSpace (EuclideanSpace ℝ (Fin n)) (Bdry n M) where
  atlas := Set.range bdryChart                 -- Problems.Geometry.stokes_bdry_chartedspace.bdryChart (from P8)
  chartAt p := bdryChart p
  mem_chart_source p := Problems.Geometry.stokes_bdry_chartedspace.main p
  chart_mem_atlas p := ⟨p, rfl⟩

end Problems.Geometry.stokes_bdry_manifold
