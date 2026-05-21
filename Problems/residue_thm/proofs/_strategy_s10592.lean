import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integral_smul_compose_monotone_reparam
import Problems.residue_thm.proofs.L_integrand_compose_eq_smul_ae

namespace Problems.residue_thm

-- Decomposition: reduce reparam invariance to (a) chain-rule a.e. integrand equality
-- and (b) monotone change-of-variables. Combine via integral_congr_ae_restrict.
theorem s10592
    {Q : ℂ → ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    (∫ t in (0 : ℝ)..1, Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t) =
      (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t)  := by
  have h_ae := integrand_compose_eq_smul_ae (Q := Q) (γ := γ) (φ := φ)
    hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  have h_cov := integral_smul_compose_monotone_reparam (Q := Q) (γ := γ) (φ := φ)
    hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  rw [intervalIntegral.integral_congr_ae_restrict h_ae]
  exact h_cov

end Problems.residue_thm
