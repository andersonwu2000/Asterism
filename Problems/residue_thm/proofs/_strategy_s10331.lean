import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_endpoint_eq_of_continuous_deriv_zero_ioo
import Problems.residue_thm.proofs.L_homotopy_integral_continuous_on_icc
import Problems.residue_thm.proofs.L_homotopy_integral_has_deriv_at_ioo

namespace Problems.residue_thm

-- Constancy via Ioo-interior derivative + Icc-continuity (avoids the boundary
-- trap of derivWithin on closed Icc that killed s10327). Let
-- J τ := ∫ t in 0..1, f (H τ t) * deriv (H τ) t. Split into:
--   (a) `homotopy_integral_continuous_on_icc` — J is continuous on [0,1]
--       (parametric integral of jointly continuous integrand);
--   (b) `homotopy_integral_has_deriv_at_ioo` — J' = 0 on the open (0,1)
--       (parametric Leibniz unlocks at interior τ via Icc 0 1 ∈ 𝓝 τ; the
--       boundary term vanishes by hH0/hH1 + Cauchy-Riemann);
--   (c) `endpoint_eq_of_continuous_deriv_zero_ioo` — generic real-analysis
--       closer: continuous on [0,1] + interior derivAt 0 ⇒ G 0 = G 1.
theorem s10331
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    (∫ t in (0:ℝ)..1, f (H 0 t) * deriv (H 0) t) =
      (∫ t in (0:ℝ)..1, f (H 1 t) * deriv (H 1) t)  := by
  have h_cont :=
    homotopy_integral_continuous_on_icc hV hf hH hHV
  have h_deriv :=
    homotopy_integral_has_deriv_at_ioo hV hf hH hHV hH0 hH1
  exact endpoint_eq_of_continuous_deriv_zero_ioo h_cont h_deriv

end Problems.residue_thm
