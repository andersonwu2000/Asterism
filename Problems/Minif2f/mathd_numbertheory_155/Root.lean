-- Direct kernel computation: the filter on Finset.Icc 100 999 has 900 elements;
-- `decide` reduces the cardinality via the kernel's `Decidable` instance and the
-- definitional unfolding of `Finset.filter`/`Finset.Icc`/`Finset.card`, closing the goal.
-- No sub-goals — leaf-bypass; avoids `native_decide` (rogue axiom).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_155.Defs
import Problems.Minif2f.mathd_numbertheory_155.proofs._strategy_s699

namespace Problems.Minif2f.mathd_numbertheory_155

def main := @Problems.Minif2f.mathd_numbertheory_155.s699

end Problems.Minif2f.mathd_numbertheory_155
