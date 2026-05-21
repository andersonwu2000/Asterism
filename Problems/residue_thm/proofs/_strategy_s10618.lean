import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_continuous_on_punctured_of_analytic
import Problems.residue_thm.proofs.L_hasderivat_from_continuous_on_segment_identity

namespace Problems.residue_thm

-- Pass ContinuousOn Q on the punctured set (rather than the prior dead s10532's
-- ContinuousAt-only hypothesis) so the parametric integrand
-- `t ↦ Q (z + t·h)` is continuous, hence AEStronglyMeasurable on [0,1] — the
-- precise gap the previous decomposition declined on.
-- (1) continuous_on_punctured_of_analytic — Builder, AnalyticOn ⇒ ContinuousOn.
-- (2) hasderivat_from_continuous_on_segment_identity — Backward analytic core:
--     ContinuousOn Q on punctured + segment identity ⇒ HasDerivAt F (Q z) z.
theorem s10618
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
  have h_cont_on : ContinuousOn Q (Set.univ \ ({a} : Set ℂ)) :=
    continuous_on_punctured_of_analytic hQ_an
  have h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h :=
    h_segment z hz
  exact hasderivat_from_continuous_on_segment_identity z hz h_cont_on h_seg

end Problems.residue_thm
