/-
  Defs.lean — owns `faceEmbed` (the boundary face embedding into the model
  `{x₀=0}`), cites `Library…CompactBdry.Bdry`. The lemma to prove (the boundary
  chart's `invFun` lands in the boundary, on-target) is the Root.
-/
import Mathlib
import Library.Geometry.ManifoldBoundary.CompactBdry

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry

namespace Problems.Geometry.stokes_bdry_invfun_mem

/-- Embed the boundary face `EuclideanSpace ℝ (Fin n)` into the model half-space as
    `{x₀ = 0}`: place `z` in coordinates `1..n` (coordinate 0 = the normal). -/
noncomputable def faceEmbed {n : ℕ} (z : EuclideanSpace ℝ (Fin n)) :
    EuclideanSpace ℝ (Fin (n + 1)) :=
  ∑ i : Fin n, z i • EuclideanSpace.basisFun (Fin (n + 1)) ℝ i.succ

end Problems.Geometry.stokes_bdry_invfun_mem
