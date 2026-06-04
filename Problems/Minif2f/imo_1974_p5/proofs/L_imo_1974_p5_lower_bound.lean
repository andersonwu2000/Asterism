-- Reduce to the raw inequality (no `s` indirection): rewrite `s` via `h₁` and
-- apply the sub-goal `lower_bound_raw`, which is the classical IMO 1974 P5
-- lower bound on the explicit fraction sum.
import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs
import Problems.Minif2f.imo_1974_p5.proofs._strategy_s9430

namespace Problems.Minif2f.imo_1974_p5

def imo_1974_p5_lower_bound := @Problems.Minif2f.imo_1974_p5.s9430

end Problems.Minif2f.imo_1974_p5
