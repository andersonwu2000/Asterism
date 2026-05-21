import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_integral_eq_primitive_diff

namespace Problems.residue_thm

-- entry_kind: Builder
-- path_integral_eq_diff_on_ball: FTC along a C¹ path on a ball,
-- specialising path_integral_eq_primitive_diff (s10318) at U := ball z₀ R.
theorem path_integral_eq_diff_on_ball
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ : ℝ → ℂ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) (Metric.ball z₀ R)) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = F (γ 1) - F (γ 0) := by
  exact path_integral_eq_primitive_diff Metric.isOpen_ball hF hγ hγU

end Problems.residue_thm
