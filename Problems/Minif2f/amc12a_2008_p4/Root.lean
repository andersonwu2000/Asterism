-- Decomposition: lift to an abstract telescoping product over `n : ℕ`.
-- Sub-goal `four_k_telescope` proves `∏ k ∈ Icc 1 n, ((4:ℝ)*k+4)/(4*k) = (n:ℝ)+1` for all `n`
-- (holds at n=0: empty product = 1 = 0+1). Main = specialize at n=501; `linarith` closes
-- using `((501:ℕ):ℝ)+1 = 502` linearly, avoiding `norm_num at h` distributing `∏` over `/`.
import Mathlib
import Problems.Minif2f.amc12a_2008_p4.Defs
import Problems.Minif2f.amc12a_2008_p4.proofs._strategy_s783

namespace Problems.Minif2f.amc12a_2008_p4

def main := @Problems.Minif2f.amc12a_2008_p4.s783

end Problems.Minif2f.amc12a_2008_p4
