import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_compact_convex_interior_homeo_closed_ball
import Problems.Topology.brouwer_fixed_point.proofs.L_realize_in_euclidean_with_interior

namespace Problems.Topology.brouwer_fixed_point

-- Decompose: K homeomorphic to a closed Euclidean ball, via two steps —
-- (a) realize K as a compact convex "fat" (nonempty-interior) subset S of some
--     EuclideanSpace ℝ (Fin n) via an affine isometry onto its affine span;
-- (b) any such S is homeomorphic to the closed unit ball there (Minkowski/gauge).
theorem s10809
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E}
    (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K)
    (hns : ¬ ∃ x : E, K = {x}) :
    ∃ (n : ℕ) (_φ : K ≃ₜ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1),
      True  := by
  obtain ⟨n, S, hSne, hScomp, hSconv, hSint, φKS⟩ :=
    realize_in_euclidean_with_interior hne hcomp hconv hns
  obtain ⟨φKS⟩ := φKS
  obtain ⟨φSB⟩ :=
    compact_convex_interior_homeo_closed_ball hSne hScomp hSconv hSint
  exact ⟨n, φKS.trans φSB, trivial⟩



end Problems.Topology.brouwer_fixed_point
