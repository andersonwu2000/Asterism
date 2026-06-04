import Mathlib
import Problems.Minif2f.amc12a_2010_p10.Defs
import Problems.Minif2f.amc12a_2010_p10.proofs.L_closed_form_with_p
import Problems.Minif2f.amc12a_2010_p10.proofs.L_p_eq_five

namespace Problems.Minif2f.amc12a_2010_p10

-- Decompose closed-form proof in two steps:
--   sub_1 `p_eq_five`: derive p = 5 from the linear system h₀ at n=1,2 with h₁..h₄
--     (no induction; pure linear arithmetic on a 1..a 4).
--   sub_2 `closed_form_with_p`: with p = 5 in hand (so a 1 = 5, a 2 = 9), induct on
--     the second-order recurrence h₀ to obtain a n = 4 n + 1 for all n.
-- The combinator chains sub_1 into sub_2; q is never needed past sub_2's hypotheses.
theorem s9259 (p q : ℝ) (a : ℕ → ℝ)
    (h₀ : ∀ n, a (n + 2) - a (n + 1) = a (n + 1) - a n)
    (h₁ : a 1 = p) (h₂ : a 2 = 9)
    (h₃ : a 3 = 3 * p - q) (h₄ : a 4 = 3 * p + q) :
    ∀ n, a n = 4 * (n : ℝ) + 1  := by
  have h_p := p_eq_five p q a h₀ h₁ h₂ h₃ h₄
  exact closed_form_with_p p q a h₀ h₁ h₂ h₃ h₄ h_p

end Problems.Minif2f.amc12a_2010_p10
