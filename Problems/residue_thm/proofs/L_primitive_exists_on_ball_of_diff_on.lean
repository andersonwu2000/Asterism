import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- primitive_exists_on_ball_of_diff_on: isExactOn_ball gives ∃ F, ∀ z ∈ ball, HasDerivAt F (f z) z

theorem primitive_exists_on_ball_of_diff_on
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : DifferentiableOn ℂ f (Metric.ball z₀ R)) :
    ∃ F : ℂ → ℂ, ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z :=
  hf.isExactOn_ball

end Problems.residue_thm

