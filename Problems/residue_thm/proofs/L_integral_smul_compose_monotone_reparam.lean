import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- integral_smul_compose_monotone_reparam: change of variables for monotone reparam via
-- integral_deriv_smul_comp_of_deriv_nonneg; uses hφ0/hφ1 to match endpoints after substitution
theorem integral_smul_compose_monotone_reparam
    {Q : ℂ → ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφmono : ∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) :
    (∫ t in (0:ℝ)..1, deriv φ t • (Q (γ (φ t)) * deriv γ (φ t))) =
      ∫ s in (0:ℝ)..1, Q (γ s) * deriv γ s := by
  have hφcont : ContinuousOn φ (Set.uIcc 0 1) := hφ.continuous.continuousOn
  have hφderiv : ∀ x ∈ Set.Ioo (min 0 1 : ℝ) (max 0 1), HasDerivAt φ (deriv φ x) x :=
    fun x _ => (hφ.differentiable (by norm_num)).differentiableAt.hasDerivAt

  have hφnonneg : ∀ x ∈ Set.Ioo (min 0 1 : ℝ) (max 0 1), 0 ≤ deriv φ x := by
    intro x hx
    simp only [min_def, max_def, if_pos (by norm_num : (0:ℝ) ≤ 1)] at hx
    exact hφmono x (Set.Ioo_subset_Icc_self hx)

  have key := intervalIntegral.integral_deriv_smul_comp_of_deriv_nonneg
    (f := φ) (f' := deriv φ) (g := fun u => Q (γ u) * deriv γ u)
    (a := (0 : ℝ)) (b := 1)
    hφcont hφderiv hφnonneg
  simp only [Function.comp_apply] at key
  rw [hφ0, hφ1] at key
  exact key

end Problems.residue_thm
