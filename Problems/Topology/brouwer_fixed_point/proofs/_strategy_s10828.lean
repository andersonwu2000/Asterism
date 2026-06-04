import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_brouwer_closed_ball_zero_case
import Problems.Topology.brouwer_fixed_point.proofs.L_fp_from_no_retraction
import Problems.Topology.brouwer_fixed_point.proofs.L_no_retraction_disk_to_sphere

namespace Problems.Topology.brouwer_fixed_point

-- Dispatch on `n`: the `n = 0` case is trivial (ambient space is subsingleton),
-- and the `n > 0` case is the substantive geometric step factored via a
-- separate no-retraction lemma.
-- Sub-goal A `brouwer_closed_ball_zero_case`: trivial; for `n = 0`,
-- `EuclideanSpace ℝ (Fin 0)` is a subsingleton so `g y = y` is forced.
-- Sub-goal B `no_retraction_disk_to_sphere`: the algebraic crux — for
-- `0 < n`, there is no continuous retraction from the closed unit ball
-- onto its boundary sphere. Uses `closed_ball_contractible_space`
-- (subsingleton `H_{n-1}` of the disk) and
-- `not_id_factor_through_subsingleton` against `H_{n-1}(Sⁿ⁻¹) ≠ 0`.
-- Sub-goal C `fp_from_no_retraction`: for `0 < n`, given no retraction,
-- extend the subtype map `g` to an ambient continuous self-map of the
-- ball with no fixed point and apply `exists_ray_retraction_of_no_fixed_point`
-- to derive a retraction, contradicting B.
theorem s10828
    {n : ℕ} (g : Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 →
                  Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
    (_hcont : Continuous g) :
    ∃ y, g y = y  := by
  rcases Nat.eq_zero_or_pos n with hn | hn
  · subst hn
    exact brouwer_closed_ball_zero_case g _hcont
  · exact fp_from_no_retraction hn (no_retraction_disk_to_sphere hn) g _hcont

end Problems.Topology.brouwer_fixed_point
