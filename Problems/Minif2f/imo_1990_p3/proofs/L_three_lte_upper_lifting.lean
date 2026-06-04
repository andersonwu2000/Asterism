-- Induction on k for the LTE-3 upper bound.
-- Base (k=0): ¬ 9 ∣ 2^m + 1 — finite case analysis mod 9.
-- Step: lift ¬ 3^(k+2) ∣ a+1 to ¬ 3^(k+3) ∣ a^3+1 with a = 2^(3^k·m), then
-- rewrite a^3 = 2^(3^(k+1)·m).  Each sub-goal drops universal scope or adds an
-- inductive hypothesis, so both are strictly simpler than the parent.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9786

namespace Problems.Minif2f.imo_1990_p3

def three_lte_upper_lifting := @Problems.Minif2f.imo_1990_p3.s9786

end Problems.Minif2f.imo_1990_p3
