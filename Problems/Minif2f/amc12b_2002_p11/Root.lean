-- Prime constraints force a=5, b=2 (only prime triplet a-2,a,a+2 is 3,5,7;
-- parity forces b=2 since both odd primes sum to even ≥ 6, not prime).
-- Then 5+2+(5-2+(5+2)) = 17, decidably prime.
import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs._strategy_s593

namespace Problems.Minif2f.amc12b_2002_p11

def main := @Problems.Minif2f.amc12b_2002_p11.s593

end Problems.Minif2f.amc12b_2002_p11
