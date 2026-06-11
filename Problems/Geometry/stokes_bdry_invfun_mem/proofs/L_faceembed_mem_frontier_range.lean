import Mathlib
import Problems.Geometry.stokes_bdry_invfun_mem.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry

namespace Problems.Geometry.stokes_bdry_invfun_mem

open scoped Manifold ContDiff

-- faceembed_mem_frontier_range: faceEmbed z lies in frontier(range 𝓡∂(n+1)) because its
-- 0-th coordinate is 0 — proved by rewriting with frontier_range_modelWithCornersEuclideanHalfSpace
-- (which characterises the frontier as {y | 0 = y 0}) then evaluating the sum via basisFun.
theorem faceembed_mem_frontier_range {n : ℕ} (z : EuclideanSpace ℝ (Fin n)) :
    faceEmbed z ∈ frontier (Set.range (𝓡∂ (n + 1))) := by
  haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
  rw [frontier_range_modelWithCornersEuclideanHalfSpace]
  simp only [Set.mem_setOf_eq]
  simp [faceEmbed, EuclideanSpace.basisFun_apply, Fin.succ_ne_zero]

end Problems.Geometry.stokes_bdry_invfun_mem
