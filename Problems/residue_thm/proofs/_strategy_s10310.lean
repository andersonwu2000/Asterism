import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_continuous_on_integrand
import Problems.residue_thm.proofs.L_differentiable_on_integral_of_continuous_on

namespace Problems.residue_thm

-- Reduce FTC differentiability of the `derivWithin`-integrand antiderivative to
-- (1) continuity of the integrand on `Icc 0 1` and (2) a generic FTC primitive lemma.
-- Sub-goal `continuous_on_integrand`: compose `ContDiffOn.continuousOn_derivWithin`
-- (γ' is continuous on `Icc 0 1`) with continuity of `γ t - a` (from `hγ.continuousOn.sub`)
-- and `havoid`-driven non-vanishing of the denominator.
-- Sub-goal `differentiable_on_integral_of_continuous_on`: abstract — for any continuous
-- `f` on `Icc 0 1`, the antiderivative `s ↦ ∫₀^s f` is `DifferentiableOn ℝ` on `Icc 0 1`
-- (FTC composition via `intervalIntegral.integral_hasDerivWithinAt_right` and `_left`).
theorem s10310
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    DifferentiableOn ℝ
      (fun s => ∫ t in (0:ℝ)..s, derivWithin γ (Set.Icc (0:ℝ) 1) t / (γ t - a))
      (Set.Icc (0:ℝ) 1)  := by
  have h_cont := continuous_on_integrand hγ hclosed havoid
  exact differentiable_on_integral_of_continuous_on hγ hclosed havoid _ h_cont

end Problems.residue_thm
