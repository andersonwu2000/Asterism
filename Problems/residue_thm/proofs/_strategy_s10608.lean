import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_smoothblend_family_collapse_aware
import Problems.residue_thm.proofs.L_glue_c2_smoothblend_family_collapse

namespace Problems.residue_thm

-- Family + glue with collapse-aware signatures: (1) for each segment i with
-- t i ≤ t (i+1), produce a σ-based blend piece ψ i landing in
-- segment (p i) (p (i+1)) with vanishing first/second endpoint derivatives;
-- the collapse hypothesis hp_collapse handles the degenerate t i = t (i+1)
-- case (forces p i = p (i+1), so the piece is the constant p i). (2) Splice
-- the family ψ into a single C² η on [0, 1] = [t 0, t n], also threaded with
-- hp_collapse to handle degenerate-interval matching.
theorem s10608
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
  have h_family :=
    c2_smoothblend_family_collapse_aware
      σ hσC2 hσ0 hσ1 hσrange hσd0 hσd1 hσdd0 hσdd1 t p htmono hp_collapse
  obtain ⟨ψ, hψ⟩ := h_family
  exact glue_c2_smoothblend_family_collapse
    t p ht0 htn htmono hp_collapse ψ hψ

end Problems.residue_thm
