import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fderiv_apply_continuous_on_icc_prod
import Problems.residue_thm.proofs.L_tau_dw_eq_fderiv_apply_on_icc_prod

namespace Problems.residue_thm

-- Reduce τ-`derivWithin` of the product `f∘H · ∂_t H` to the partial of the
-- joint function `g(q) = f(H q.1 q.2) · fderivWithin (H ·.1 ·.2) at (q,(0,1))`
-- applied in direction (1,0). `tau_dw_eq_fderiv_apply_on_icc_prod` provides the
-- pointwise equality on `Icc×Icc`; `fderiv_apply_continuous_on_icc_prod` gives
-- joint continuity of that smooth side. `ContinuousOn.congr` transports.
theorem s10357
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ContinuousOn
      (fun p : ℝ × ℝ => derivWithin
          (fun τ'' => f (H τ'' p.1) * derivWithin (H τ'') (Set.Icc (0:ℝ) 1) p.1)
          (Set.Icc (0:ℝ) 1) p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) := by
  have h_eq := tau_dw_eq_fderiv_apply_on_icc_prod hV hf hH hHV hH0 hH1
  have h_cont := fderiv_apply_continuous_on_icc_prod hV hf hH hHV hH0 hH1
  exact h_cont.congr h_eq

end Problems.residue_thm
