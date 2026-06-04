import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_continuous_ray_parameter_of_nonzero
import Problems.Topology.brouwer_fixed_point.proofs.L_sphere_inner_diff_nonneg

namespace Problems.Topology.brouwer_fixed_point

-- Reduce to abstract quadratic-root construction: setting v(x) = x - f(x),
-- v is continuous (hcont), nowhere zero (hnofp), and satisfies the sphere
-- inner-positivity ⟨x, v(x)⟩ ≥ 0 (hmaps + Cauchy–Schwarz). The substantive
-- sub-goal eliminates f entirely and builds t purely from these abstract
-- conditions on v.
theorem s10820
    {n : ℕ} (hn : 0 < n)
    {f : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hcont : ContinuousOn f (Metric.closedBall 0 1))
    (hmaps : Set.MapsTo f
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1))
    (hnofp : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, f x ≠ x) :
    ∃ t : EuclideanSpace ℝ (Fin n) → ℝ,
      ContinuousOn t (Metric.closedBall 0 1) ∧
      (∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1,
          ‖x + t x • (x - f x)‖ = 1) ∧
      (∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, t x = 0)  := by
  have hv_cont : ContinuousOn (fun x : EuclideanSpace ℝ (Fin n) => x - f x)
      (Metric.closedBall 0 1) :=
    continuousOn_id.sub hcont
  have hv_ne : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1,
      (fun x : EuclideanSpace ℝ (Fin n) => x - f x) x ≠ 0 := by
    intro x hx hzero
    have hxfx : x = f x := sub_eq_zero.mp hzero
    exact hnofp x hx hxfx.symm
  have h_inner :
      ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1,
        0 ≤ @inner ℝ _ _ x ((fun x : EuclideanSpace ℝ (Fin n) => x - f x) x) := by
    intro x hx
    exact sphere_inner_diff_nonneg hn hmaps x hx
  exact continuous_ray_parameter_of_nonzero hn hv_cont hv_ne h_inner

end Problems.Topology.brouwer_fixed_point
