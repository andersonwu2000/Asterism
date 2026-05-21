import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_differentiable_integral_deriv_within
import Problems.residue_thm.proofs.L_integral_eq_integral_deriv_within

namespace Problems.residue_thm

-- Switch `deriv γ` for `derivWithin γ (Icc 0 1)` inside the integrand. They agree
-- on `Ioo 0 1` (i.e. a.e. on the integration interval), so the integrals coincide,
-- but `derivWithin γ (Icc 0 1)` is cleanly continuous on `Icc 0 1` via
-- `ContDiffOn.continuousOn_derivWithin` — unlike `deriv γ`, which can carry junk
-- values at endpoints when `γ` is only `ContDiffOn` rather than globally `ContDiff`.
-- Sub-goal 1 (`integral_eq_integral_deriv_within`): pointwise integral equality on
-- `Icc 0 1` (a.e.-equal integrands → `intervalIntegral.integral_congr_ae`).
-- Sub-goal 2 (`differentiable_integral_deriv_within`): FTC differentiability of the
-- `derivWithin`-integrand antiderivative. Closer transfers via `DifferentiableOn.congr`.
theorem s10306
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    DifferentiableOn ℝ
      (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
      (Set.Icc (0:ℝ) 1)  := by
  have h_eq := integral_eq_integral_deriv_within hγ hclosed havoid
  have h_diff := differentiable_integral_deriv_within hγ hclosed havoid
  exact h_diff.congr h_eq

end Problems.residue_thm
