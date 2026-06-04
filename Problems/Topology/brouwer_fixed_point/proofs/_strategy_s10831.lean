import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_ray_retraction_of_subtype_no_fp

namespace Problems.Topology.brouwer_fixed_point

-- Contrapositive: assume no fixed point of `g`, then construct the
-- forbidden retraction directly from the no-fp data and contradict
-- `_hno_retr`. The retraction construction (subtype-`g` → ambient
-- self-map → ray retraction via the proved sibling
-- `exists_ray_retraction_of_no_fixed_point`) is the only substantive
-- step; bundle it into a single sub-goal so the strategy patch only
-- references one new lemma.
-- Sub-goal `ray_retraction_of_subtype_no_fp`: strictly simpler — its
-- hypothesis set contains the negation of the parent's conclusion
-- (`hnofp`), which is precisely the data needed to feed
-- `exists_ray_retraction_of_no_fixed_point` after extending `g` to an
-- ambient map of the closed ball.
theorem s10831
    {n : ℕ} (_hn : 0 < n)
    (_hno_retr : ¬ ∃ r : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n),
      ContinuousOn r (Metric.closedBall 0 1) ∧
      Set.MapsTo r (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1) ∧
      ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, r x = x)
    (g : Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 →
         Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
    (_hcont : Continuous g) :
    ∃ y, g y = y  := by
  by_contra h
  push Not at h
  exact _hno_retr (ray_retraction_of_subtype_no_fp _hn _hno_retr g _hcont h)

end Problems.Topology.brouwer_fixed_point
