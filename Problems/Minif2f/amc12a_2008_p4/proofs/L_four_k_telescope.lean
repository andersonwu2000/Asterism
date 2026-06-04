-- Decomposition: induction on `n`.
-- `four_k_telescope_zero` handles the empty product at n=0.
-- `four_k_telescope_succ` extends from n to n+1 given the IH; closes the inductive step.
import Mathlib
import Problems.Minif2f.amc12a_2008_p4.Defs
import Problems.Minif2f.amc12a_2008_p4.proofs._strategy_s9274

namespace Problems.Minif2f.amc12a_2008_p4

def four_k_telescope := @Problems.Minif2f.amc12a_2008_p4.s9274

end Problems.Minif2f.amc12a_2008_p4
