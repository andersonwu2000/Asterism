import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_f_h_continuous_on_icc
import Problems.residue_thm.proofs.L_partial_tau_h_continuous_on_icc

namespace Problems.residue_thm

-- ContinuousOn (f ∘ H τ * ∂_τ' H(·,t)) on Icc 0 1 via ContinuousOn.mul.
-- (1) f_h_continuous_on_icc: continuity of f ∘ H τ on Icc — composition of analytic f
--     with the C² slice H τ, mapped into V; pure Builder leaf.
-- (2) partial_tau_h_continuous_on_icc: continuity of the τ-partial derivative slice
--     `t ↦ derivWithin (H · t) (Icc 0 1) τ` on Icc — from C² of the joint H, the partial
--     in τ is a continuous function of (τ,t) on the closed square; Backward.
theorem s10338
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1,
      ContinuousOn
        (fun t => f (H τ t) * derivWithin (fun τ' => H τ' t) (Set.Icc (0:ℝ) 1) τ)
        (Set.Icc (0:ℝ) 1) := by
  have h_f_h := f_h_continuous_on_icc hV hf hH hHV hH0 hH1
  have h_dw := partial_tau_h_continuous_on_icc hV hf hH hHV hH0 hH1
  intro τ hτ
  exact (h_f_h τ hτ).mul (h_dw τ hτ)

end Problems.residue_thm
