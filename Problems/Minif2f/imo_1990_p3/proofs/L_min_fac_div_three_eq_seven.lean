-- Reduce to a pure ZMod statement: q := Nat.minFac (m/3) is prime ≥ 5
-- (sub-goal `min_fac_div_three_prime_ge_five`, identical to an already-proved
-- lemma — framework alias resolves it). With that primality + range data, the
-- sub-goal `eq_seven_of_prime_ge_five_two_pow_six` packages the ZMod →
-- ℕ-divisibility bridge (q ∣ 63) and the prime classification: q = 7.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9864

namespace Problems.Minif2f.imo_1990_p3

def min_fac_div_three_eq_seven := @Problems.Minif2f.imo_1990_p3.s9864

end Problems.Minif2f.imo_1990_p3
