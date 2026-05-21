import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_derivwithin_gamma_comp_phi_chain_at_one
import Problems.residue_thm.proofs.L_derivwithin_phi_eq_zero_at_one

namespace Problems.residue_thm

-- Chain rule split: derivWithin (γ∘φ) (Icc 0 1) 1 factors as
-- (derivWithin γ (Icc 0 1) (φ 1)) * (derivWithin φ (Icc 0 1) 1).
-- Sub-goal (A): derivWithin φ (Icc 0 1) 1 = 0 (uses hφ, hφd1; ContDiff ⇒ deriv = derivWithin).
-- Sub-goal (B): chain rule equation (uses hγ, hφ, hφrange; via MapsTo + DifferentiableWithinAt.comp).
-- Combinator: rewrite by (B), then (A), then mul_zero. Both sub-goals strictly simpler:
-- (A) drops γ entirely; (B) drops hφd1 and becomes a generic chain-rule identity.
theorem s10598
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφd1 : deriv φ 1 = 0) :
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0  := by
  have hA : derivWithin φ (Set.Icc 0 1) 1 = 0 :=
    derivwithin_phi_eq_zero_at_one hφ hφd1
  have hB : derivWithin (γ ∘ φ) (Set.Icc 0 1) 1
      = derivWithin γ (Set.Icc 0 1) (φ 1) * derivWithin φ (Set.Icc 0 1) 1 :=
    derivwithin_gamma_comp_phi_chain_at_one hγ hφ hφrange
  rw [hB, hA]; simp

end Problems.residue_thm
