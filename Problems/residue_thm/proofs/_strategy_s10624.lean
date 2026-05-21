import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chain_rule_compose_reparam_pointwise_ioo

namespace Problems.residue_thm

-- Decomposition: replace the a.e.-on-uIoc claim with the pointwise chain rule
-- on the open interval Ioo 0 1 (full measure in uIoc 0 1).  The pointwise
-- sub-goal absorbs the technical boundary handling (φ t may hit Icc-endpoints,
-- where γ is only differentiable within Icc); the patch then upgrades the
-- pointwise equality to an a.e. equality on the closed half-open interval.
theorem s10624
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    ∀ᵐ t ∂(MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) 1)),
      deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t)  := by
  have hpw : ∀ t ∈ Set.Ioo (0:ℝ) 1,
      deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t) :=
    chain_rule_compose_reparam_pointwise_ioo hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  rw [show Set.uIoc (0:ℝ) 1 = Set.Ioc 0 1 from Set.uIoc_of_le zero_le_one,
      ← MeasureTheory.restrict_Ioo_eq_restrict_Ioc]
  refine (MeasureTheory.ae_restrict_iff' measurableSet_Ioo).2 ?_
  exact Filter.Eventually.of_forall hpw
end Problems.residue_thm
