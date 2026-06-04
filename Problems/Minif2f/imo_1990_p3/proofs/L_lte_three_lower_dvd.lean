-- Reduce LTE-style lower bound to a clean k,m-parametrized lifting helper:
-- write n = 3^k * m where k = v_3(n) and m = ord_compl[3] n is odd & 3-coprime,
-- then the helper proves 3^(k+1) ∣ 2^(3^k*m)+1 by induction on k.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9728

namespace Problems.Minif2f.imo_1990_p3

def lte_three_lower_dvd := @Problems.Minif2f.imo_1990_p3.s9728

end Problems.Minif2f.imo_1990_p3
