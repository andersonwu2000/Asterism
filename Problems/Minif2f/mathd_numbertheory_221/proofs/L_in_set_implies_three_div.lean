import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs

namespace Problems.Minif2f.mathd_numbertheory_221

-- in_set_implies_three_div: fin_cases on membership, decide per element with raised recursion depth
set_option maxRecDepth 2000 in
theorem in_set_implies_three_div :
    ∀ x : ℕ,
    x ∈ ({4, 9, 25, 49, 121, 169, 289, 361, 529, 841, 961} : Finset ℕ) →
    (0 < x ∧ x < 1000 ∧ x.divisors.card = 3) := by
  intro x hx
  fin_cases hx <;> decide

end Problems.Minif2f.mathd_numbertheory_221
