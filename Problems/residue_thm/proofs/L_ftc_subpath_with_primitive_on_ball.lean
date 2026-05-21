import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10534

namespace Problems.residue_thm

-- ftc_subpath_with_primitive_on_ball: FTC along a C¹ path given a primitive on the ball;
-- aliases s10534 which splits via intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le.
theorem ftc_subpath_with_primitive_on_ball
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ : ℝ → ℂ} {a b : ℝ}
    (hab : a ≤ b)
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc a b))
    (hγU : Set.MapsTo γ (Set.Icc a b) (Metric.ball z₀ R)) :
    (∫ t in a..b, f (γ t) * deriv γ t) = F (γ b) - F (γ a) := by
  exact s10534 hab hF hγ hγU

end Problems.residue_thm

