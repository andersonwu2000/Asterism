import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_ftc_subpath_with_primitive_on_ball
import Problems.residue_thm.proofs.L_primitive_exists_on_ball_of_diff_on

namespace Problems.residue_thm
-- Decompose primitive-with-FTC bundle into (a) primitive existence on the ball
-- from `hf` alone, and (b) FTC along the C¹ sub-path on `Icc a b` given any
-- such primitive. Combinator pairs the obtained primitive `F` with its FTC
-- equation. Sub-goal (a) is a one-liner via Mathlib `DifferentiableOn.isExactOn_ball`;
-- sub-goal (b) is the proved sibling shape `path_int_eq_diff_on_ball_subinterval`.
theorem s10540
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ : ℝ → ℂ} {a b : ℝ}
    (hab : a ≤ b)
    (hf : DifferentiableOn ℂ f (Metric.ball z₀ R))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc a b))
    (hγU : Set.MapsTo γ (Set.Icc a b) (Metric.ball z₀ R)) :
    ∃ F : ℂ → ℂ,
      (∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z) ∧
      (∫ t in a..b, f (γ t) * deriv γ t) = F (γ b) - F (γ a)  := by
  obtain ⟨F, hF⟩ := primitive_exists_on_ball_of_diff_on hf
  exact ⟨F, hF, ftc_subpath_with_primitive_on_ball hab hF hγ hγU⟩

end Problems.residue_thm
