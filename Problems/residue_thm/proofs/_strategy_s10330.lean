import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integral_tau_partial_eq_boundary
import Problems.residue_thm.proofs.L_tau_deriv_integral_eq_integral_tau_partial

namespace Problems.residue_thm

-- Split the τ-derivative-of-integral analysis into:
-- (A) `tau_deriv_integral_eq_integral_tau_partial` — differentiation under the
--     integral sign: the τ-derivative of the parameter-dependent integral
--     equals the integral of the τ-partial of the integrand.
-- (B) `integral_tau_partial_eq_boundary` — Clairaut + Cauchy–Riemann +
--     FTC: the pointwise τ-partial of `f(H τ' t)·∂_t H(τ',t)` is the t-total
--     derivative of `f(H τ' t)·∂_τH(τ',t)`, so its t-integral collapses to
--     the boundary expression.
-- Closer: rewrite (A) then (B).
theorem s10330
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1,
      derivWithin
        (fun τ' => ∫ t in (0:ℝ)..1, f (H τ' t) * deriv (H τ') t)
        (Set.Icc (0:ℝ) 1) τ
        = f (H τ 1) * derivWithin (fun τ' => H τ' 1) (Set.Icc (0:ℝ) 1) τ
          - f (H τ 0) * derivWithin (fun τ' => H τ' 0) (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ
  have hA := tau_deriv_integral_eq_integral_tau_partial hV hf hH hHV hH0 hH1 τ hτ
  have hB := integral_tau_partial_eq_boundary hV hf hH hHV hH0 hH1 τ hτ
  rw [hA, hB]

end Problems.residue_thm
