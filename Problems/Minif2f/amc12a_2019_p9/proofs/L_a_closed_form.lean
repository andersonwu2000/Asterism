-- Decompose closed-form proof into two base cases + an inductive step.
-- base_one/base_two pin a 1, a 2 to the closed form (h₀/h₁ are literal).
-- induction_step is the algebraic core: given the closed form at k+1 and k+2,
-- derive it at k+3 via the recurrence h₂ (k+1).
-- Combinator: bundle (a (k+1), a (k+2)) into a pair invariant, prove by Nat
-- induction (zero ↦ ⟨base_one, base_two⟩; succ ↦ slide window via induction_step),
-- then extract `a n` for `n = m+1` (n ≥ 1 ⇒ ∃ m, n = m+1).
import Mathlib
import Problems.Minif2f.amc12a_2019_p9.Defs
import Problems.Minif2f.amc12a_2019_p9.proofs._strategy_s9355

namespace Problems.Minif2f.amc12a_2019_p9

def a_closed_form := @Problems.Minif2f.amc12a_2019_p9.s9355

end Problems.Minif2f.amc12a_2019_p9
