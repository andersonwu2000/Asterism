-- Reduce the residue-1 bound to one closed-form sub-goal:
-- `(∑ k∈Icc 1 (4n+1), k*I^k).im = 2n+1`. With `m = 4(m/4)+1` (omega
-- from `m%4=1`), rewriting m makes the parent goal `2*(m/4)+1 ≤ 48`,
-- which `linarith` closes from `m/4 ≤ 23` (since `m < 97`).
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9720

namespace Problems.Minif2f.amc12a_2009_p15

def sum_im_mod1 := @Problems.Minif2f.amc12a_2009_p15.s9720

end Problems.Minif2f.amc12a_2009_p15
