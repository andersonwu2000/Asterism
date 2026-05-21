import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_const_derivwithin_icc_zero
import Problems.residue_thm.proofs.L_tau_deriv_integral_formula

namespace Problems.residue_thm

-- Reduce τ-derivative-of-integral = 0 to:
-- (1) `tau_deriv_integral_formula` — the τ-derivative equals the boundary
--     term `f(H τ 1)·∂_τH(τ,1) − f(H τ 0)·∂_τH(τ,0)` (the analytic core:
--     differentiation under the integral + Clairaut + Cauchy–Riemann).
-- (2) `const_derivwithin_icc_zero` — generic: a function constant on
--     `Icc 0 1` has `derivWithin = 0`. Applied to `τ ↦ H τ 0` (via `hH0`)
--     and `τ ↦ H τ 1` (via `hH1`).
-- Closer: rewrite formula + both endpoint derivatives, then `ring`.
theorem s10328
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, derivWithin
      (fun τ => ∫ t in (0:ℝ)..1, f (H τ t) * deriv (H τ) t)
      (Set.Icc (0:ℝ) 1) τ = 0 := by
  intro τ hτ
  have h_formula := tau_deriv_integral_formula hV hf hH hHV hH0 hH1 τ hτ
  have h_d0 : derivWithin (fun τ' => H τ' 0) (Set.Icc (0:ℝ) 1) τ = 0 :=
    const_derivwithin_icc_zero (g := fun τ' => H τ' 0)
      (fun τ' hτ' => by simpa using hH0 τ' hτ') τ hτ
  have h_d1 : derivWithin (fun τ' => H τ' 1) (Set.Icc (0:ℝ) 1) τ = 0 :=
    const_derivwithin_icc_zero (g := fun τ' => H τ' 1)
      (fun τ' hτ' => by simpa using hH1 τ' hτ') τ hτ
  rw [h_formula, h_d0, h_d1]
  ring

end Problems.residue_thm
