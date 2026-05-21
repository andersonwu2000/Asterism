import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrand_joint_continuous_on_ball_icc
import Problems.residue_thm.proofs.L_param_int_continuous_on_ball_of_joint

namespace Problems.residue_thm

-- Decompose parametric integral continuity into (i) joint continuity of the
-- integrand on `ball z r ×ˢ Icc 0 1` (uses `derivWithin γ` continuous on Icc
-- via `ContDiffOn.continuousOn_derivWithin`, plus `γ t - w ≠ 0` since γ avoids
-- ball z r and w ∈ ball z r), and (ii) a generic bridge transporting joint
-- ContinuousOn on `(open w-set) ×ˢ Icc 0 1` to ContinuousOn of the parametric
-- interval-integral on the w-set (pointwise DCT with constant bound from
-- compactness of `closedBall w₀ ρ ×ˢ Icc 0 1`).
theorem s10612
    {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hr : 0 < r)
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, r < dist (γ t) z) :
    ContinuousOn
      (fun w => ∫ t in (0:ℝ)..1, derivWithin γ (Set.Icc 0 1) t / (γ t - w))
      (Metric.ball z r)  := by
  have h_joint := integrand_joint_continuous_on_ball_icc hγ hr h_avoid
  exact param_int_continuous_on_ball_of_joint hr h_joint

end Problems.residue_thm
