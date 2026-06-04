import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_brouwer_closed_ball
import Problems.Topology.brouwer_fixed_point.proofs.L_fixed_point_transfer_via_homeo

namespace Problems.Topology.brouwer_fixed_point

-- Decompose into the closed-ball Brouwer fixed-point theorem and the
-- pure-topology transport along the subtype homeomorphism `φ`.
-- Sub-goal A `brouwer_closed_ball`: any continuous self-map of the closed
-- unit ball in `EuclideanSpace ℝ (Fin n)` has a fixed point. This is the
-- substantive geometric step (uses the proved Forward lemmas
-- `exists_ray_retraction_of_no_fixed_point`,
-- `closed_ball_contractible_space`, `not_id_factor_through_subsingleton`
-- to derive a contradiction from the absence of a fixed point; handles
-- `n = 0` separately since the ball is then a singleton).
-- Sub-goal B `fixed_point_transfer_via_homeo`: a generic topological
-- transport — given any subtype homeomorphism `φ : S ≃ₜ T` and a
-- Brouwer-style fact on `T`, deduce the corresponding fact on `S` for any
-- self-map `f` of `S` (pure continuity / point-set bookkeeping).
theorem s10827
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E} {n : ℕ}
    (φ : K ≃ₜ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
    {f : E → E} (hcont : ContinuousOn f K) (hmaps : Set.MapsTo f K K) :
    ∃ x ∈ K, f x = x  := by
  exact fixed_point_transfer_via_homeo φ hcont hmaps brouwer_closed_ball

end Problems.Topology.brouwer_fixed_point
