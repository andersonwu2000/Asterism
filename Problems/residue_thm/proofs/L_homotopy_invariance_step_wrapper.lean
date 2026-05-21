import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_homotopy_integral_continuous_on_icc
import Problems.residue_thm.proofs.L_homotopy_integral_has_deriv_at_ioo
import Problems.residue_thm.proofs.L_endpoint_eq_of_continuous_deriv_zero_ioo

namespace Problems.residue_thm

-- homotopy_invariance_step_wrapper: delegates to proved homotopy-invariance
-- sub-goals (continuous J on Icc + deriv J = 0 on Ioo → J 0 = J 1)
theorem homotopy_invariance_step_wrapper
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    (∫ t in (0:ℝ)..1, f (H 0 t) * deriv (H 0) t) =
      (∫ t in (0:ℝ)..1, f (H 1 t) * deriv (H 1) t) := by
  have h_cont := homotopy_integral_continuous_on_icc hV hf hH hHV
  have h_deriv := homotopy_integral_has_deriv_at_ioo hV hf hH hHV hH0 hH1
  exact endpoint_eq_of_continuous_deriv_zero_ioo h_cont h_deriv

end Problems.residue_thm

