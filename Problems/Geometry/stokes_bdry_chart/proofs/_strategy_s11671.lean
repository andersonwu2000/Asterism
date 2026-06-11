import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs.L_chart_left_inv
import Problems.Geometry.stokes_bdry_chart.proofs.L_chart_map_source
import Problems.Geometry.stokes_bdry_chart.proofs.L_chart_map_target
import Problems.Geometry.stokes_bdry_chart.proofs.L_chart_right_inv

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

namespace Problems.Geometry.stokes_bdry_chart

-- 4-way conjunction split: one sub-goal per partial-equiv law.
-- map_source/map_target/left_inv/right_inv each combine bricks B
-- (face_embed_face_proj_of_coord_zero) and C (boundary_ext_chart_at_coord_zero)
-- with the corresponding PartialEquiv law; each is strictly smaller than the 4-way ∧.
theorem s11671 : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M),
    (∀ q ∈ chartSource p, chartToFun p q ∈ chartTarget p) ∧
    (∀ z ∈ chartTarget p, chartInvFun p z ∈ chartSource p) ∧
    (∀ q ∈ chartSource p, chartInvFun p (chartToFun p q) = q) ∧
    (∀ z ∈ chartTarget p, chartToFun p (chartInvFun p z) = z)  := by
  intro n M _ _ _ p
  have h_chart_map_source := chart_map_source p
  have h_chart_map_target := chart_map_target p
  have h_chart_left_inv := chart_left_inv p
  have h_chart_right_inv := chart_right_inv p
  exact ⟨h_chart_map_source, h_chart_map_target, h_chart_left_inv, h_chart_right_inv⟩

end Problems.Geometry.stokes_bdry_chart

