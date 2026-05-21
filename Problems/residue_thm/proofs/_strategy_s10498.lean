import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_hasderivat_from_segment_identity
import Problems.residue_thm.proofs.L_segment_path_integral_identity

namespace Problems.residue_thm

-- Straight-line segment trick: for each z ≠ a, use hF on γ_h(t)=z+t·h with
-- ‖h‖<dist z a to get F(z+h)-F z = ∫₀¹ Q(z+t·h)·h dt (h_seg), then combine
-- with continuity of Q at z (from hQ_an) to conclude HasDerivAt F (Q z) z.
theorem s10498
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    (F : ℂ → ℂ)
    (hF : ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), HasDerivAt F (Q z) z  := by
  have h_seg := segment_path_integral_identity hQ_an h_loops F hF
  exact hasderivat_from_segment_identity hQ_an h_loops F hF h_seg
end Problems.residue_thm
