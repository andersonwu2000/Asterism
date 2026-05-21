import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_family_of_smooth_blend_segment_pieces
import Problems.residue_thm.proofs.L_glue_c2_segment_pieces_to_global

namespace Problems.residue_thm

-- Build η via σ-based piecewise blending: (1) produce a σ-blend piece on each
-- segment with C², MapsTo into the segment, and derivWithin / (derivWithin)²
-- vanishing at both endpoints; (2) glue the family of C² pieces with vanishing
-- endpoint derivatives into a single global C² η on [0,1].
theorem s10562
    (σ : ℝ → ℝ) (hσC2 : ContDiff ℝ 2 σ) (hσ0 : σ 0 = 0) (hσ1 : σ 1 = 1)
    (hσrange : ∀ τ, τ ∈ Set.Icc (0:ℝ) 1 → σ τ ∈ Set.Icc (0:ℝ) 1)
    (hσd0 : deriv σ 0 = 0) (hσd1 : deriv σ 1 = 0)
    (hσdd0 : deriv (deriv σ) 0 = 0) (hσdd1 : deriv (deriv σ) 1 = 0)
    {n : ℕ} (t : ℕ → ℝ) (p : ℕ → ℂ)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i + 1))
    (hp_collapse : ∀ i, i < n → t i = t (i + 1) → p i = p (i + 1)) :
    ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      (∀ i, i ≤ n → η (t i) = p i) ∧
      (∀ i, i < n →
        Set.MapsTo η (Set.Icc (t i) (t (i + 1))) (segment ℝ (p i) (p (i + 1))))  := by
  have h_pieces := family_of_smooth_blend_segment_pieces
    σ hσC2 hσ0 hσ1 hσrange hσd0 hσd1 hσdd0 hσdd1 t p htmono
  have h_glue := glue_c2_segment_pieces_to_global
    t p ht0 htn htmono hp_collapse
  obtain ⟨ψ, hψ⟩ := h_pieces
  exact h_glue ψ hψ

end Problems.residue_thm
