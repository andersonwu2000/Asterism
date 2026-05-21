import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_reparam_compose_non_integral_props
import Problems.residue_thm.proofs.L_reparam_compose_path_integral_invariant
import Problems.residue_thm.proofs.L_smooth_reparam_unit_flat_endpoints_exists

namespace Problems.residue_thm

-- Decompose: pick a fixed smooth reparametrization φ : ℝ → ℝ of [0,1]
-- with φ(0)=0, φ(1)=1 and deriv φ flat at both endpoints (existence
-- via `smooth_reparam_unit_flat_endpoints_exists`); set γ' = γ ∘ φ,
-- transfer the six non-integral properties (C¹, endpoint match, flat
-- derivWithin at 0/1, avoidance) through the composition lemma
-- `reparam_compose_non_integral_props`, and reduce the integral
-- identity to the change-of-variables fact
-- `reparam_compose_path_integral_invariant`.
theorem s10548
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
  obtain ⟨φ, hφC1, hφ0, hφ1, hφd0, hφd1, hφrange⟩ :=
    smooth_reparam_unit_flat_endpoints_exists
  have h_props :
      ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) ∧
      (γ ∘ φ) 0 = γ 0 ∧
      (γ ∘ φ) 1 = γ 1 ∧
      derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0 ∧
      derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a) :=
    reparam_compose_non_integral_props (a := a) hγ havoid hφC1 hφ0 hφ1 hφd0 hφd1 hφrange
  have h_int :
      (∫ t in (0 : ℝ)..1, Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t) =
        (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t) :=
    reparam_compose_path_integral_invariant (Q := Q) hγ hφC1 hφ0 hφ1 hφd0 hφd1 hφrange
  exact ⟨γ ∘ φ, h_props.1, h_props.2.1, h_props.2.2.1, h_props.2.2.2.1,
         h_props.2.2.2.2.1, h_props.2.2.2.2.2, h_int⟩

end Problems.residue_thm
