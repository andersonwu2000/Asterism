-- Refute `p ∣ m` by reducing to the ZMod identity `(2:ZMod p)^2 = 1`, then
-- inline the standard `p ∣ 3` contradiction (since `prime_ge_five_not_two_sq_eq_one`
-- is not auto-imported here). Sub-goal `two_sq_eq_one_given_no_seven` carries the
-- entire order-of-2 / gcd(2m,p-1)=2 argument; ¬7∣m collapses the only case where
-- gcd-of-2 fails (p=7 with 3∣m forcing gcd(2m,p-1)=6 ⊃ 2).
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9825

namespace Problems.Minif2f.imo_1990_p3

def no_prime_ge_five_dvd_given_no_seven := @Problems.Minif2f.imo_1990_p3.s9825

end Problems.Minif2f.imo_1990_p3
