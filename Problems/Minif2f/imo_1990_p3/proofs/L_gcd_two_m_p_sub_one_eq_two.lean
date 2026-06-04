-- Vacuity reduction: the hypotheses (m ≥ 2, m²∣2^m+1, 3∣m, ¬9∣m, ¬7∣m)
-- force m = 3 (IMO 1990 P3 conclusion); under m = 3 no prime p ≥ 5 can
-- divide m, so the ∀ p body — including the gcd equality — is vacuous.
-- One sub-goal: `m_eq_three_given_hypotheses` (the IMO conclusion).
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9846

namespace Problems.Minif2f.imo_1990_p3

def gcd_two_m_p_sub_one_eq_two := @Problems.Minif2f.imo_1990_p3.s9846

end Problems.Minif2f.imo_1990_p3
