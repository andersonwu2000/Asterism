import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_inv_fun_continuous_on
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_source_is_open
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_is_open
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_to_fun_continuous_on

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

-- Split the 4-way conjunction into one sub-goal per conjunct.
-- Each conjunct is independent; the combinator is the anonymous constructor.
theorem s11676 : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M),
    IsOpen (chartSource p) ∧ IsOpen (chartTarget p) ∧
    ContinuousOn (chartToFun p) (chartSource p) ∧
    ContinuousOn (chartInvFun p) (chartTarget p)  := by
  intro n M _ _ _ p
  have h_src : IsOpen (chartSource p) := chart_source_is_open p
  have h_tgt : IsOpen (chartTarget p) := chart_target_is_open p
  have h_to : ContinuousOn (chartToFun p) (chartSource p) := chart_to_fun_continuous_on p
  have h_inv : ContinuousOn (chartInvFun p) (chartTarget p) := chart_inv_fun_continuous_on p
  exact ⟨h_src, h_tgt, h_to, h_inv⟩

end Problems.Geometry.stokes_bdry_chart_topo

