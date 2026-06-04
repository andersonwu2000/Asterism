-- Direct proof: split Icc 1 1319 = Icc 1 659 ⊔ Icc 660 1319 via Ico-consecutive.
-- Convert each Icc to Ico (Icc a b = Ico a (b+1)) so Finset.sum_Ico_consecutive applies,
-- giving sum_low + sum_high = sum_all; rearrange with linarith. Leaf — no sub-goals.
import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs._strategy_s9650

namespace Problems.Minif2f.imo_1979_p1

def tail_eq_full_minus_head := @Problems.Minif2f.imo_1979_p1.s9650

end Problems.Minif2f.imo_1979_p1
