import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_exp_partial_path_int_mul_eq

namespace Problems.residue_thm

-- Reduce `exp(∫ deriv γ /(γ-a)) = 1` to constancy of `s ↦ exp(G(s))·(γ 0-a)`
-- where `G(s) = ∫₀ˢ deriv γ /(γ-a)`. The sub-goal `exp_partial_path_int_mul_eq`
-- packages the constancy as `exp(G(s))·(γ 0-a) = γ s - a` on [0,1]; specialise
-- to s=1, rewrite γ 1 ↦ γ 0 via `hclosed`, cancel `γ 0 - a ≠ 0` (from `havoid 0`)
-- with `mul_left_eq_self₀` to extract `exp(G(1)) = 1`.
theorem s10301
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    Complex.exp (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 1  := by
  have h_const := exp_partial_path_int_mul_eq hγ hclosed havoid
  have h1 := h_const 1 ⟨zero_le_one, le_refl 1⟩
  rw [← hclosed] at h1
  have hne : γ 0 - a ≠ 0 :=
    sub_ne_zero.mpr (havoid 0 ⟨le_refl 0, zero_le_one⟩)
  exact (mul_left_eq_self₀.mp h1).resolve_right hne

end Problems.residue_thm
