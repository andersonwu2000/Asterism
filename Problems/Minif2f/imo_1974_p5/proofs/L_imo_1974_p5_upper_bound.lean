-- Split `s < 2` into 4 mediant inequalities (one per fraction in `s`).
-- Each is `x/(denom) < (x+y)/(a+b+c+d)`; summing the 4 strict inequalities
-- gives `s < 2(a+c)/(a+b+c+d) + 2(b+d)/(a+b+c+d) = 2`.
import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs
import Problems.Minif2f.imo_1974_p5.proofs._strategy_s9491

namespace Problems.Minif2f.imo_1974_p5

def imo_1974_p5_upper_bound := @Problems.Minif2f.imo_1974_p5.s9491

end Problems.Minif2f.imo_1974_p5
