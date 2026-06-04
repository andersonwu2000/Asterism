-- Combine three sub-claims via orderOf chain:
-- 2^(2m)=1 (from m²∣2^m+1 + p∣m) and 2^(p-1)=1 (Fermat) give orderOf 2 ∣ gcd(2m,p-1);
-- with gcd=2 (needing ¬7∣m to kill the p=7 case), conclude orderOf 2 ∣ 2 ⇒ 2^2 = 1.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9833

namespace Problems.Minif2f.imo_1990_p3

def two_sq_eq_one_given_no_seven := @Problems.Minif2f.imo_1990_p3.s9833

end Problems.Minif2f.imo_1990_p3
