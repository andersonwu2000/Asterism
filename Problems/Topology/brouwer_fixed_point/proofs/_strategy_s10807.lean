import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_homeomorph_closed_ball_of_not_singleton

namespace Problems.Topology.brouwer_fixed_point

-- Case-split on whether K is a singleton; the singleton case closes the
-- left disjunct directly, the non-singleton case is the substantive
-- homeomorphism (delegated to `homeomorph_closed_ball_of_not_singleton`).
theorem s10807
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E}
    (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K) :
    (∃ x : E, K = {x}) ∨
    (∃ (n : ℕ) (_φ : K ≃ₜ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1),
      True)  := by
  by_cases hs : ∃ x : E, K = {x}
  · exact Or.inl hs
  · have h_homeo :=
      homeomorph_closed_ball_of_not_singleton hne hcomp hconv hs
    exact Or.inr h_homeo

end Problems.Topology.brouwer_fixed_point
