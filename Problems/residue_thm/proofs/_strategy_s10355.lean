import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fderiv_section_chain_rule_in_t
import Problems.residue_thm.proofs.L_schwarz_mixed_partial_bridge

namespace Problems.residue_thm

-- Schwarz mixed-partial decomposition. Two sub-goals:
-- (A) `fderiv_section_chain_rule_in_t` — chain rule: the t-section of the joint
--     fderivWithin's (1,0)-application has, at t ∈ Ioo, derivative equal to the
--     iterated `fderivWithin (fderivWithin H s) s (τ,t) (0,1) (1,0)`.
-- (B) `schwarz_mixed_partial_bridge` — bridge: that iterated value equals
--     `derivWithin (fun τ' => deriv (H τ') t) (Icc 0 1) τ`, via second-derivative
--     symmetry (`ContDiffWithinAt.isSymmSndFDerivWithinAt`) plus the t-slice
--     chain rule connecting `deriv (H τ') t` to `fderivWithin H s (τ',t) (0,1)`.
-- Combine via `HasDerivAt.congr_deriv hA hB`.
theorem s10355
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt
        (fun t' => (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t')) (1, 0))
        (derivWithin (fun τ' => deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ) t  := by
  intro τ hτ t ht
  have hA := fderiv_section_chain_rule_in_t hV hf hH hHV hH0 hH1 τ hτ t ht
  have hB := schwarz_mixed_partial_bridge hV hf hH hHV hH0 hH1 τ hτ t ht
  exact hA.congr_deriv hB


end Problems.residue_thm
