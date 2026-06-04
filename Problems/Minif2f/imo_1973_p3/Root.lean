-- Decompose via the substitution y = x + 1/x (since x ≠ 0): from existence of a real
-- root x of the quartic, build y with y^2 ≥ 4 and a*y + b = 2 - y^2 (reduce_to_y_substitution);
-- then bound a^2 + b^2 ≥ 4/5 (bound_via_cauchy_schwarz) by Cauchy-Schwarz plus y^2 ≥ 4.
import Mathlib
import Problems.Minif2f.imo_1973_p3.Defs
import Problems.Minif2f.imo_1973_p3.proofs._strategy_s610

namespace Problems.Minif2f.imo_1973_p3

def main := @Problems.Minif2f.imo_1973_p3.s610

end Problems.Minif2f.imo_1973_p3
