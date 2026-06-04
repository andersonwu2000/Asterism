-- Pivot to q := Nat.minFac (m/3) (smallest prime factor of m above 3) instead of arbitrary p.
-- Two sub-goals: (1) q is prime ≥ 5; (2) (2:ZMod q)^2 = 1 (the hard lemma — uses minimality
-- of q and ¬7∣m to collapse the order argument).  Closer: (2:ZMod q)^2 = 1 forces 3=0 in
-- ZMod q, so q ∣ 3, contradicting q ≥ 5.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9853

namespace Problems.Minif2f.imo_1990_p3

def false_of_prime_ne_seven_dvd := @Problems.Minif2f.imo_1990_p3.s9853

end Problems.Minif2f.imo_1990_p3
