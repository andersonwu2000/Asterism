import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_homeomorph_closed_ball_of_not_singleton

namespace Problems.Topology.brouwer_fixed_point

-- brouwer_homeo_dispatch: singleton-or-ball dispatch using homeomorph_closed_ball_of_not_singleton
-- Case-splits on whether K is a singleton (left disjunct) or not (right disjunct).
-- Delegates the non-singleton case to the already-proved s10807 alias.
theorem brouwer_homeo_dispatch
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E}
    (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K) :
    (∃ x : E, K = {x}) ∨
    (∃ (n : ℕ) (_φ : K ≃ₜ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1),
      True) := by
  by_cases hs : ∃ x : E, K = {x}
  · exact Or.inl hs
  · exact Or.inr (homeomorph_closed_ball_of_not_singleton hne hcomp hconv hs)

end Problems.Topology.brouwer_fixed_point
