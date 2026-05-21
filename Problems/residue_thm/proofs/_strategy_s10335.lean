import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_g_continuous_on_icc
import Problems.residue_thm.proofs.L_g_has_deriv_at_ioo
import Problems.residue_thm.proofs.L_x_interval_integrable

namespace Problems.residue_thm

-- FTC in `t` against the antiderivative `G(t) := f(H τ t) · ∂_τ' H(τ', t)|_{τ'=τ}`.
-- The integrand `X(t) := ∂_τ' (f(H τ' t) · ∂_t H(τ', t))|_{τ'=τ}` equals `dG/dt` on the
-- interior via the product rule + Schwarz (`H` is C²), giving
-- `∫₀¹ X = G 1 - G 0 = f(H τ 1)·∂_τ' H(·,1) − f(H τ 0)·∂_τ' H(·,0)`.
-- Sub-goals: (1) `g_continuous_on_icc` — antiderivative continuous on `Icc 0 1`;
-- (2) `g_has_deriv_at_ioo` — Schwarz/chain rule interior identity `dG/dt = X` on `Ioo 0 1`;
-- (3) `x_interval_integrable` — integrand interval-integrable on `[0,1]`.
theorem s10335
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1,
      (∫ t in (0:ℝ)..1,
          derivWithin (fun τ' => f (H τ' t) * deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ)
        = f (H τ 1) * derivWithin (fun τ' => H τ' 1) (Set.Icc (0:ℝ) 1) τ
          - f (H τ 0) * derivWithin (fun τ' => H τ' 0) (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ
  have h_cont := g_continuous_on_icc hV hf hH hHV hH0 hH1 τ hτ
  have h_hderiv := g_has_deriv_at_ioo hV hf hH hHV hH0 hH1 τ hτ
  have h_int := x_interval_integrable hV hf hH hHV hH0 hH1 τ hτ
  exact intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le zero_le_one h_cont h_hderiv h_int

end Problems.residue_thm
