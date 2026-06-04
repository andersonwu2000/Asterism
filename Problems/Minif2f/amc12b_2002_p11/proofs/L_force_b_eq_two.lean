-- Case-split on `b` via `Nat.Prime.eq_two_or_odd`: either b = 2 (done), or b is odd.
-- The odd case is delegated to `odd_b_contradiction`, which uses the parity
-- constraint plus the four prime hypotheses to derive False.
import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs._strategy_s9327

namespace Problems.Minif2f.amc12b_2002_p11

def force_b_eq_two := @Problems.Minif2f.amc12b_2002_p11.s9327

end Problems.Minif2f.amc12b_2002_p11
