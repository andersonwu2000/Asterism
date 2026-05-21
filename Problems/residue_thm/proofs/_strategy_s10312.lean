import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_h_deriv_integral_dw

namespace Problems.residue_thm

-- Chain-rule decomposition for `exp(-G(s))` where `G(s) = ∫₀ˢ deriv γ t / (γ t - a)`.
-- Sub-goal `h_deriv_integral_dw`: FTC for the integral, output derivative is
-- `derivWithin γ (Icc 0 1) s / (γ s - a)` (uses derivWithin, not deriv, to match
-- the parent's strategy s10311 — avoids the s10307 junk-at-endpoints issue).
-- Closer: `.neg.cexp` produces `exp(-G(s)) * -(derivWithin γ (Icc 0 1) s / (γ s - a))`;
-- `mul_comm` aligns with the target derivative shape.
theorem s10312
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
        (-(derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a)) *
           Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
        (Set.Icc (0:ℝ) 1) s  := by
  intro s hs
  have h_int : HasDerivWithinAt
      (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
      (derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a))
      (Set.Icc (0:ℝ) 1) s := h_deriv_integral_dw hγ hclosed havoid s hs
  have h_neg : HasDerivWithinAt
      (fun s => -(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)))
      (-(derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a)))
      (Set.Icc (0:ℝ) 1) s := h_int.neg
  have h_exp : HasDerivWithinAt
      (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
      (Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))) *
         -(derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a)))
      (Set.Icc (0:ℝ) 1) s := h_neg.cexp
  rw [mul_comm]
  exact h_exp

end Problems.residue_thm
