-- Direct bound: if a+b ≤ 18 then 0 < a² + ab + b² ≤ (a+b)² ≤ 324 < 343 = 7³,
-- contradicting 7³ ∣ a² + ab + b² via Int.le_of_dvd. The ¬7∣ hypotheses are unused.
import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs
import Problems.Minif2f.imo_1984_p2.proofs._strategy_s9424

namespace Problems.Minif2f.imo_1984_p2

def bound_from_div := @Problems.Minif2f.imo_1984_p2.s9424

end Problems.Minif2f.imo_1984_p2
