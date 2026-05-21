import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_reparam_compose_c1_non_integral_props_v2
import Problems.residue_thm.proofs.L_reparam_compose_path_integral_invariant_monotone
import Problems.residue_thm.proofs.L_smooth_reparam_hermite_monotone_exists

namespace Problems.residue_thm

-- Thread monotonicity through the change-of-variables step: pick a smooth, monotone
-- Hermite reparametrization φ of [0,1] (existence with `0 ≤ deriv φ`), transfer the
-- non-integral C¹/endpoint/flat-derivWithin/avoid properties through the composition,
-- and close the integral identity via the monotone-φ variant of change-of-variables.
theorem s10579
    {Q : ℂ → ℂ} {a : ℂ} {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∃ γ' : ℝ → ℂ,
      ContDiffOn ℝ 1 γ' (Set.Icc 0 1) ∧
      γ' 0 = γ 0 ∧
      γ' 1 = γ 1 ∧
      derivWithin γ' (Set.Icc 0 1) 0 = 0 ∧
      derivWithin γ' (Set.Icc 0 1) 1 = 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, γ' t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (γ' t) * deriv γ' t) =
        (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t)  := by
  have h_smooth_reparam_hermite_monotone_exists :=
    smooth_reparam_hermite_monotone_exists
  obtain ⟨φ, hφ, hφ0, hφ1, hφd0, hφd1, hφrange, hφmono⟩ :=
    h_smooth_reparam_hermite_monotone_exists
  have h_reparam_compose_c1_non_integral_props_v2 :=
    reparam_compose_c1_non_integral_props_v2 hγ havoid hφ hφ0 hφ1 hφd0 hφd1 hφrange
  obtain ⟨hcomp, hcomp0, hcomp1, hcompd0, hcompd1, hcompav⟩ :=
    h_reparam_compose_c1_non_integral_props_v2
  have h_reparam_compose_path_integral_invariant_monotone :=
    reparam_compose_path_integral_invariant_monotone (Q := Q)
      hγ hφ hφ0 hφ1 hφd0 hφd1 hφrange hφmono
  exact ⟨γ ∘ φ, hcomp, hcomp0, hcomp1, hcompd0, hcompd1, hcompav,
    h_reparam_compose_path_integral_invariant_monotone⟩

end Problems.residue_thm
