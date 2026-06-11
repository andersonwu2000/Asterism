import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_inv_fun_val_eq_symm_face_embed
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_continuous_on_symm_comp_face_embed

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

-- Reduce continuity of `chartInvFun` to continuity of `(extChartAt _ p.val).symm ∘ faceEmbed`
-- via the subtype-inducing map `Subtype.val : Bdry n M → M`: on `chartTarget p` the `dite`
-- in `chartInvFun` always takes the then-branch (sub-goal 1, value identity), and the
-- then-branch composite is continuous on `chartTarget p` (sub-goal 2).
-- `IsInducing.continuousOn_iff` + `ContinuousOn.congr` combine the two.

theorem s11677 {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M) : ContinuousOn (chartInvFun p) (chartTarget p)  := by
  have h_val_eq : ∀ z ∈ chartTarget p,
      (chartInvFun p z).val = (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z) :=
    chart_inv_fun_val_eq_symm_face_embed p
  have h_cont_symm : ContinuousOn
      (fun z : EuclideanSpace ℝ (Fin n) => (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z))
      (chartTarget p) :=
    continuous_on_symm_comp_face_embed p
  have h_ind : Topology.IsInducing (Subtype.val : Bdry n M → M) :=
    Topology.IsInducing.subtypeVal
  exact h_ind.continuousOn_iff.mpr (h_cont_symm.congr fun z hz => h_val_eq z hz)



end Problems.Geometry.stokes_bdry_chart_topo

