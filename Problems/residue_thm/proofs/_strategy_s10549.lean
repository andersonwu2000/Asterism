import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_piecewise_lerp_in_segments_given_smoothstep
import Problems.residue_thm.proofs.L_smoothstep_c2_with_zero_endpoint_derivs

namespace Problems.residue_thm

-- Build η in two pieces: (1) an abstract C² smoothstep σ : ℝ → ℝ with σ(0)=0,
-- σ(1)=1, σ([0,1])⊆[0,1] and σ′, σ″ vanishing at 0,1 — yields C² gluing without
-- any explicit polynomial; (2) given such σ, the parametric piecewise lerp η is
-- C² on Icc 0 1 and lands in each segment, by σ-based convex blending.
theorem s10549
    {n : ℕ} (t : ℕ → ℝ) (p : ℕ → ℂ)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i + 1))
    (hp_collapse : ∀ i, i < n → t i = t (i + 1) → p i = p (i + 1)) :
    ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      (∀ i, i ≤ n → η (t i) = p i) ∧
      (∀ i, i < n →
        Set.MapsTo η (Set.Icc (t i) (t (i + 1))) (segment ℝ (p i) (p (i + 1))))  := by
  have h_smoothstep := smoothstep_c2_with_zero_endpoint_derivs
  obtain ⟨σ, hσC2, hσ0, hσ1, hσrange, hσd0, hσd1, hσdd0, hσdd1⟩ := h_smoothstep
  exact c2_piecewise_lerp_in_segments_given_smoothstep
    σ hσC2 hσ0 hσ1 hσrange hσd0 hσd1 hσdd0 hσdd1
    t p ht0 htn htmono hp_collapse



end Problems.residue_thm
