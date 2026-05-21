import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_deriv_exp_neg_path_zero
import Problems.residue_thm.proofs.L_differentiable_exp_neg_path

namespace Problems.residue_thm

-- Reduce constancy of `H(s) = exp(-G(s))·(γ s - a)` (where `G(s) = ∫₀ˢ deriv γ /(γ-a)`)
-- to two prerequisites — H is differentiable on `[0,1]` and `derivWithin H [0,1] = 0` on
-- the interior `[0,1)` — and close via `constant_of_derivWithin_zero`. Evaluate at s=0
-- to identify H 0 = γ 0 - a (since the (0..0) integral vanishes), then multiply both
-- sides of `H(s) = γ 0 - a` by `exp(G(s))` and use `exp_add`+`exp_zero` to rearrange
-- to the target shape `exp(G(s))·(γ 0 - a) = γ s - a`.
theorem s10302
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Icc (0:ℝ) 1,
      Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) * (γ 0 - a) = γ s - a  := by
  set H : ℝ → ℂ := fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) *
                              (γ s - a) with hH_def
  have h_diff : DifferentiableOn ℝ H (Set.Icc (0:ℝ) 1) :=
    differentiable_exp_neg_path hγ hclosed havoid
  have h_deriv_zero : ∀ s ∈ Set.Ico (0:ℝ) 1, derivWithin H (Set.Icc (0:ℝ) 1) s = 0 :=
    deriv_exp_neg_path_zero hγ hclosed havoid
  have h_constant : ∀ s ∈ Set.Icc (0:ℝ) 1, H s = H 0 :=
    constant_of_derivWithin_zero h_diff h_deriv_zero
  have h_H0 : H 0 = γ 0 - a := by
    simp [hH_def, intervalIntegral.integral_same]
  intro s hs
  have h_inv : Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a) =
               γ 0 - a := by
    have := (h_constant s hs).trans h_H0
    simpa [hH_def] using this
  have hexp_cancel : Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) *
                     Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) = 1 := by
    rw [← Complex.exp_add]
    simp
  calc Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) * (γ 0 - a)
      = Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) *
          (Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a)) := by
        rw [h_inv]
    _ = (Complex.exp (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) *
          Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)))) * (γ s - a) := by ring
    _ = 1 * (γ s - a) := by rw [hexp_cancel]
    _ = γ s - a := by ring

end Problems.residue_thm
