import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chain_rule_compose_reparam_ae

namespace Problems.residue_thm

-- Decomposition: reduce the a.e. chain-rule equation to the bare pointwise chain rule
-- `deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t)` a.e. on Ioc 0 1.
-- After the substitution, `mul_smul_comm` rebalances the scalar across the product with `Q`.
theorem s10611
    {Q : ℂ → ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    ∀ᵐ t ∂(MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) 1)),
      Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t =
        deriv φ t • (Q (γ (φ t)) * deriv γ (φ t))  := by
  have h_chain := chain_rule_compose_reparam_ae hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  filter_upwards [h_chain] with t ht
  simp only [Function.comp_apply, ht, mul_smul_comm]



end Problems.residue_thm
