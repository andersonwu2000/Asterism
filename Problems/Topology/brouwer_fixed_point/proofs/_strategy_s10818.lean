import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_exists_continuous_ray_parameter
import Problems.Topology.brouwer_fixed_point.proofs.L_ray_retraction_from_parameter

namespace Problems.Topology.brouwer_fixed_point

-- Build the retraction r(x) := x + t(x) • (x - f(x)) by the classic
-- ray-from-f(x)-through-x construction.
-- Sub-goal A produces the scaling parameter t : Dⁿ → ℝ (continuous on Dⁿ,
-- normalising the ray-endpoint to the sphere, vanishing on Sⁿ⁻¹) — the
-- geometric crux (uses hmaps + hnofp).
-- Sub-goal B assembles r from any such t (pure algebra; needs only hcont
-- and continuity of t).
theorem s10818
    {n : ℕ} (hn : 0 < n)
    {f : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hcont : ContinuousOn f (Metric.closedBall 0 1))
    (hmaps : Set.MapsTo f
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1))
    (hnofp : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, f x ≠ x) :
    ∃ r : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n),
      ContinuousOn r (Metric.closedBall 0 1) ∧
      Set.MapsTo r
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1) ∧
      ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, r x = x  := by
  have h_param := exists_continuous_ray_parameter hn hcont hmaps hnofp
  obtain ⟨t, htcont, htnorm, htsphere⟩ := h_param
  exact ray_retraction_from_parameter hcont t htcont htnorm htsphere

end Problems.Topology.brouwer_fixed_point
