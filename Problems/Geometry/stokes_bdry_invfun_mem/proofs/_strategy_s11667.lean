import Mathlib
import Problems.Geometry.stokes_bdry_invfun_mem.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.proofs.L_faceembed_mem_frontier_range
import Problems.Geometry.stokes_bdry_invfun_mem.proofs.L_symm_mem_boundary_of_frontier

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_bdry_invfun_mem

open scoped Manifold ContDiff
open Library.Geometry.ManifoldBoundary.CompactBdry

-- Decomposition: (A) model-side computation — `faceEmbed z` lies in the frontier of the
-- half-space model's range (its 0-th coordinate vanishes); (B) chart transfer — any
-- on-target point of `frontier (range 𝓡∂(n+1))` is pulled back by the extended chart's
-- symm into the manifold boundary. Root = B at `x := p.val`, `y := faceEmbed z`, fed by A.
theorem s11667 : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M) (z : EuclideanSpace ℝ (Fin n)),
    faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target →
      (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z) ∈ (𝓡∂ (n + 1)).boundary M  := by
  intro n M _ _ _ p z hy
  have h_face_frontier := faceembed_mem_frontier_range z
  have h_transfer := symm_mem_boundary_of_frontier p.val (faceEmbed z) hy h_face_frontier
  exact h_transfer

end Problems.Geometry.stokes_bdry_invfun_mem
