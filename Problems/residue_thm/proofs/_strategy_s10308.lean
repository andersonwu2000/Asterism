import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_h_deriv_integral

namespace Problems.residue_thm

-- Chain rule + FTC: derivative of `exp(-∫₀ˢ deriv γ t / (γ t - a) dt)`.
-- Sub `h_deriv_integral` gives FTC for the integral itself (continuous integrand from `havoid`),
-- then `.neg.cexp` yields the chain rule and `mul_comm` reorders the product to match.
theorem s10308
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
        (-(deriv γ s / (γ s - a)) *
           Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
        (Set.Icc (0:ℝ) 1) s  := by
  intro s hs
  have h1 : HasDerivWithinAt (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
              (deriv γ s / (γ s - a)) (Set.Icc (0:ℝ) 1) s :=
    h_deriv_integral hγ hclosed havoid s hs
  have h2 : HasDerivWithinAt
              (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
              (Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) *
                -(deriv γ s / (γ s - a)))
              (Set.Icc (0:ℝ) 1) s := h1.neg.cexp
  rw [mul_comm]
  exact h2

end Problems.residue_thm
