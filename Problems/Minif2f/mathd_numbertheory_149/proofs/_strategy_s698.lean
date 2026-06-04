import Mathlib
import Problems.Minif2f.mathd_numbertheory_149.Defs

namespace Problems.Minif2f.mathd_numbertheory_149

-- Concrete finite sum: filter predicate is decidable, range is finite, so `decide` evaluates both sides.
-- Only k=21 and k=45 in [0,50) satisfy k%8=5 ∧ k%6=3; 21+45 = 66.
theorem s698 : (∑ k ∈ Finset.filter (fun x => x % 8 = 5 ∧ x % 6 = 3) (Finset.range 50), k) = 66  := by
  decide

end Problems.Minif2f.mathd_numbertheory_149
