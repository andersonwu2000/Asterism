import Mathlib
import Problems.Minif2f.mathd_numbertheory_211.Defs

namespace Problems.Minif2f.mathd_numbertheory_211

-- Goal `Finset.card (filter ...) = 20` is fully decidable: filter predicate is decidable,
-- Finset.range 60 is concrete, both sides reduce to a numeral. `decide` closes it.
theorem s706 : Finset.card (Finset.filter (fun n => 6 ∣ 4 * ↑n - (2 : ℤ)) (Finset.range 60)) = 20  := by
  decide

end Problems.Minif2f.mathd_numbertheory_211
