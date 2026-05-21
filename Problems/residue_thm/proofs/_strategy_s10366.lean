import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_deriv_within_section_fderiv_eq_deriv
import Problems.residue_thm.proofs.L_iterated_fderiv_eq_tau_section_deriv_within
import Problems.residue_thm.proofs.L_mixed_partial_schwarz_swap

namespace Problems.residue_thm

-- Schwarz mixed-partial bridge. Decompose via three rewrites:
-- (A) Symmetry of the iterated `fderivWithin` (Schwarz) swaps the directions (0,1)/(1,0).
-- (B) The (1,0)-direction iterated fderivWithin at (τ,t) equals the τ-section
--     `derivWithin (fun τ' => fderivWithin H U (τ',t) (0,1)) (Icc 0 1) τ` (lesson-34
--     pattern, applied on the τ-side).
-- (C) The inner section `fun τ' => fderivWithin H U (τ',t) (0,1)` agrees on `Icc 0 1`
--     with `fun τ' => deriv (H τ') t` (lesson-34 pattern in the t-direction; uses
--     `t ∈ Ioo 0 1` so `Icc 0 1 ∈ 𝓝 t`), giving equal `derivWithin`s.
-- Combine via three `.trans`'s.
theorem s10366
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      (fderivWithin ℝ (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) (0, 1) (1, 0) =
        derivWithin (fun τ' => deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ t ht
  have h_schwarz := mixed_partial_schwarz_swap hH τ hτ t ht
  have h_tau_section := iterated_fderiv_eq_tau_section_deriv_within hH τ hτ t ht
  have h_inner_congr := deriv_within_section_fderiv_eq_deriv hH τ hτ t ht
  exact h_schwarz.trans (h_tau_section.trans h_inner_congr)

end Problems.residue_thm
