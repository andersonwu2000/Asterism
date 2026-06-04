-- Direct induction on `n`. Base case: empty product. Successor: split off last term via
-- `Finset.prod_insert` after rewriting `Icc 1 (n+1) = insert (n+1) (Icc 1 n)`, apply IH,
-- simplify with `field_simp` (the `(4:ℝ)*(n+1)` divisor is nonzero by `positivity`).
import Mathlib
import Problems.Minif2f.amc12a_2008_p4.Defs
import Problems.Minif2f.amc12a_2008_p4.proofs._strategy_s9362

namespace Problems.Minif2f.amc12a_2008_p4

def prod_telescope_general := @Problems.Minif2f.amc12a_2008_p4.s9362

end Problems.Minif2f.amc12a_2008_p4
