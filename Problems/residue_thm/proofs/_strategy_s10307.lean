import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_h_deriv_exp
import Problems.residue_thm.proofs.L_h_deriv_gamma_sub

namespace Problems.residue_thm

-- Product-rule decomposition of `H(s) = exp(-G(s)) · (γ s - a)`:
-- sub `h_deriv_exp` gives the derivative of the `exp(-∫)` factor (chain rule + FTC,
-- requires `γ t ≠ a` for integrand regularity), sub `h_deriv_gamma_sub` gives
-- derivative of `γ s - a` (just `deriv γ s`). Combine via `HasDerivWithinAt.mul`.
theorem s10307
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a))
        (-(deriv γ s / (γ s - a)) *
           Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * (γ s - a) +
         Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) * deriv γ s)
        (Set.Icc (0:ℝ) 1) s  := by
  intro s hs
  have h_deriv_exp := h_deriv_exp hγ hclosed havoid s hs
  have h_deriv_gamma_sub := h_deriv_gamma_sub hγ hclosed havoid s hs
  exact h_deriv_exp.mul h_deriv_gamma_sub

end Problems.residue_thm
