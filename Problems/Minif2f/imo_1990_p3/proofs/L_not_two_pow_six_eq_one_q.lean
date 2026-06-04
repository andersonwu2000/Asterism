-- Decompose by reducing False to a contradiction with `¬ 7 ∣ m`.
-- Sub-goal `min_fac_div_three_eq_seven` shows `Nat.minFac (m/3) = 7` from the
-- `(2 : ZMod q)^6 = 1` hypothesis (q ∣ 63, q prime ≥ 5 ⇒ q = 7). Combinator:
-- `Nat.minFac_dvd` lifts 7 ∣ m/3 to 7 ∣ m via `m = 3*(m/3)`, contradicting h7m.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9863

namespace Problems.Minif2f.imo_1990_p3

def not_two_pow_six_eq_one_q := @Problems.Minif2f.imo_1990_p3.s9863

end Problems.Minif2f.imo_1990_p3
