import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_continuous_at_of_analytic_on_punctured
import Problems.residue_thm.proofs.L_hasderivat_from_segment_integral

namespace Problems.residue_thm

-- Pointwise dispatch: for each z ≠ a, combine continuity of Q at z (from analyticity)
-- with the segment-integral identity F(z+h)-F z = ∫₀¹ Q(z+t·h)·h dt to conclude
-- HasDerivAt F (Q z) z.
-- Sub-goals: (1) continuous_at_of_analytic_on_punctured — Builder:
--   open-set analytic ⇒ ContinuousAt.
-- (2) hasderivat_from_segment_integral — Backward: the analytic core
--   (continuity at z + segment ID on Metric.ball z (dist z a) ⇒ HasDerivAt).
theorem s10508
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    (F : ℂ → ℂ)
    (hF : ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t)
    (h_segment : ∀ z ∈ Set.univ \ ({a} : Set ℂ), ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), HasDerivAt F (Q z) z  := by
  intro z hz
  have h_cont : ContinuousAt Q z := continuous_at_of_analytic_on_punctured hQ_an z hz
  have h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h := h_segment z hz
  exact hasderivat_from_segment_integral hz h_cont h_seg

end Problems.residue_thm
