import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integral_one_sub_substitution
import Problems.residue_thm.proofs.L_integral_reverse_chain_neg

namespace Problems.residue_thm

-- Decompose path-reversal sign-flip into (a) chain rule + a.e. swap so the LHS becomes
-- `-(∫ Q(β(1-t)) * deriv β (1-t))` and (b) substitution `u = 1 - t` equating the
-- two unsigned integrals.
theorem s10546
    {Q : ℂ → ℂ} {a : ℂ} {β : ℝ → ℂ}
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
    (∫ t in (0 : ℝ)..1, Q (β (1 - t)) * deriv (fun s => β (1 - s)) t) =
      -(∫ t in (0 : ℝ)..1, Q (β t) * deriv β t)  := by
  have h_neg := integral_reverse_chain_neg (Q := Q) (a := a) hβ hβ_avoid
  have h_sub := integral_one_sub_substitution (Q := Q) (a := a) hβ hβ_avoid
  rw [h_neg, h_sub]

end Problems.residue_thm
