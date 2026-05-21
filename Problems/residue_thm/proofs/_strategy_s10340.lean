import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_x_clean_continuous_on_icc
import Problems.residue_thm.proofs.L_x_clean_eq_orig_ae

namespace Problems.residue_thm

-- Reduce IntervalIntegrable to ContinuousOn (Icc 0 1) on a "clean" integrand that uses
-- `derivWithin (H τ') (Icc 0 1) t` instead of `deriv (H τ') t`, then transfer via congr_ae.
-- Sub-goals: (1) `x_clean_continuous_on_icc` — clean integrand is continuous on `Icc 0 1`;
-- (2) `x_clean_eq_orig_ae` — clean ≡ original a.e. on `uIoc 0 1` (they agree on `Ioo 0 1`
-- since `derivWithin (H τ') (Icc 0 1) t = deriv (H τ') t` for `t ∈ Ioo 0 1`).
theorem s10340
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1,
      IntervalIntegrable
        (fun t => derivWithin (fun τ' => f (H τ' t) * deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ)
        MeasureTheory.volume 0 1  := by
  intro τ hτ
  have h_cont := x_clean_continuous_on_icc hV hf hH hHV hH0 hH1 τ hτ
  have h_ae := x_clean_eq_orig_ae hV hf hH hHV hH0 hH1 τ hτ
  exact (h_cont.intervalIntegrable_of_Icc (by norm_num : (0:ℝ) ≤ 1)).congr_ae h_ae

end Problems.residue_thm
