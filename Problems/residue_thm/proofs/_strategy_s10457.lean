import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_g_along_path_intvl_integrable
import Problems.residue_thm.proofs.L_pointwise_integrand_decomp
import Problems.residue_thm.proofs.L_principal_along_path_intvl_integrable

namespace Problems.residue_thm

-- Apply the pointwise decomposition `hpw` at `γ t` (valid since γ maps into U \ T),
-- multiply by `deriv γ t`, then lift via integration linearity.
-- Sub-goals:
--   (1) `pointwise_integrand_decomp` — the pointwise equality of integrands on Icc 0 1.
--   (2) `g_along_path_intvl_integrable` — integrability of `g ∘ γ * γ'` on [0,1].
--   (3) `principal_along_path_intvl_integrable` — for each `a ∈ T`, integrability of
--       `P a ∘ γ * γ'` on [0,1].
-- Combinator: `intervalIntegral.integral_congr` swaps the integrand on uIcc 0 1, then
-- `intervalIntegral.integral_add` splits the sum, then `intervalIntegral.integral_finsetSum`
-- pushes the Finset.sum out of the integral.
theorem s10457
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ)
    (hg : AnalyticOn ℂ g U)
    (hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}))
    (hpw : ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
      (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) +
      ∑ a ∈ T, ∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t  := by
  have h_pw_Icc :=
    pointwise_integrand_decomp hU hT hf hγ hmaps g P hg hPa hpw
  have h_g_int :=
    g_along_path_intvl_integrable hU hT hf hγ hmaps g P hg hPa hpw
  have h_P_int :=
    principal_along_path_intvl_integrable hU hT hf hγ hmaps g P hg hPa hpw

  have h_sum_int : IntervalIntegrable (fun t => ∑ a ∈ T, P a (γ t) * deriv γ t)
                    MeasureTheory.volume 0 1 := by
    have hsum := IntervalIntegrable.sum (μ := MeasureTheory.volume) (a := (0:ℝ)) (b := 1)
              T (f := fun a t => P a (γ t) * deriv γ t)
              (fun a ha => h_P_int a ha)
    convert hsum using 1
    funext t
    simp [Finset.sum_apply]

  have h_pw_uIcc : Set.EqOn (fun t => f (γ t) * deriv γ t)
                            (fun t => g (γ t) * deriv γ t + ∑ a ∈ T, P a (γ t) * deriv γ t)
                            (Set.uIcc (0:ℝ) 1) := by
    rw [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1)]
    intro t ht
    exact h_pw_Icc t ht
  rw [intervalIntegral.integral_congr h_pw_uIcc,
      intervalIntegral.integral_add h_g_int h_sum_int,
      intervalIntegral.integral_finsetSum (fun a ha => h_P_int a ha)]


end Problems.residue_thm
