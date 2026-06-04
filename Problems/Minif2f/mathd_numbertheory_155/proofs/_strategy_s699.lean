import Mathlib
import Problems.Minif2f.mathd_numbertheory_155.Defs

namespace Problems.Minif2f.mathd_numbertheory_155

-- Direct kernel computation: the filter on Finset.Icc 100 999 has 900 elements;
-- `decide` reduces the cardinality via the kernel's `Decidable` instance and the
-- definitional unfolding of `Finset.filter`/`Finset.Icc`/`Finset.card`, closing the goal.
-- No sub-goals — leaf-bypass; avoids `native_decide` (rogue axiom).
theorem s699 : Finset.card (Finset.filter (fun x => x % 19 = 7) (Finset.Icc 100 999)) = 48  := by
  decide

end Problems.Minif2f.mathd_numbertheory_155
