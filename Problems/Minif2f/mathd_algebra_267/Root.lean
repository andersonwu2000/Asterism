-- Direct proof: x≠1, x≠-2 give nonzero denominators; field_simp turns
-- the equation into the polynomial identity (x+1)(x+2) = (x-2)(x-1),
-- which simplifies to 6x = 0, closed by linarith.
import Mathlib
import Problems.Minif2f.mathd_algebra_267.Defs
import Problems.Minif2f.mathd_algebra_267.proofs._strategy_s657

namespace Problems.Minif2f.mathd_algebra_267

def main := @Problems.Minif2f.mathd_algebra_267.s657

end Problems.Minif2f.mathd_algebra_267
