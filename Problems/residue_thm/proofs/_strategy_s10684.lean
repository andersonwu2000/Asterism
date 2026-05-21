import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_h_deriv_eq_two_beta_deriv_interior

namespace Problems.residue_thm

-- Reduce integral equality on [1/2,1] to pointwise a.e. equality on Ioo (1/2) 1.
-- Sub-goal `h_deriv_eq_two_beta_deriv_interior` supplies the chain-rule equation
-- `deriv h t = 2 * deriv β' (2*t - 1)` on the open interior; combined with the
-- parent hypothesis `hh_right` for the Q-factor, this closes the integrand
-- equation a.e. on Ioc (1/2) 1 (since Ioo and Ioc differ by {1}, a measure-zero set).
theorem s10684
    {Q : ℂ → ℂ} {β' h : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_right : ∀ t ∈ Set.Icc ((1/2) : ℝ) 1, h t = β' (2*t - 1)) :
    (∫ t in ((1/2) : ℝ)..1, Q (h t) * deriv h t) =
      (∫ t in ((1/2) : ℝ)..1, Q (β' (2*t - 1)) * (2 * deriv β' (2*t - 1)))  := by
  have hkey : ∀ t ∈ Set.Ioo ((1:ℝ)/2) 1, deriv h t = 2 * deriv β' (2*t - 1) :=
    h_deriv_eq_two_beta_deriv_interior hβ' hh hh_right
  apply intervalIntegral.integral_congr_ae_restrict
  rw [Set.uIoc_of_le (by norm_num : ((1:ℝ)/2) ≤ 1)]
  refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict MeasureTheory.Ioo_ae_eq_Ioc ?_
  filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
  have ht_Icc : t ∈ Set.Icc ((1:ℝ)/2) 1 := Set.Ioo_subset_Icc_self ht
  rw [hh_right t ht_Icc, hkey t ht]

end Problems.residue_thm
