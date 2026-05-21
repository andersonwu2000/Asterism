import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_has_deriv_within_at_dw_integral
import Problems.residue_thm.proofs.L_integral_eq_integral_deriv_within_2

namespace Problems.residue_thm

-- FTC for `∫₀ˢ deriv γ t / (γ t - a)` with derivative value
-- `derivWithin γ (Icc 0 1) s / (γ s - a)`. Direct FTC fails because `deriv γ` is junk at
-- endpoints (Icc 0 1 ∉ nhds 0/1), so the integrand is not continuous on Icc; swap to the
-- `derivWithin`-integrand which IS continuous on Icc, apply FTC there, then transfer.
-- Sub-goal `has_deriv_within_at_dw_integral` (Backward): FTC for the derivWithin version.
-- Sub-goal `integral_eq_integral_deriv_within_2` (Builder): integrals agree pointwise on
-- Icc 0 1 (integrands differ only at endpoints, a measure-zero set).
-- Combinator: `HasDerivWithinAt.congr` swaps the integrand-function side.
theorem s10313
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
        (derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a))
        (Set.Icc (0:ℝ) 1) s  := by
  intro s hs
  have hs_icc : s ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hs
  have h_ftc := has_deriv_within_at_dw_integral hγ hclosed havoid s hs
  have h_eq := integral_eq_integral_deriv_within_2 hγ hclosed havoid
  exact h_ftc.congr (fun y hy => h_eq y hy) (h_eq s hs_icc)

end Problems.residue_thm
