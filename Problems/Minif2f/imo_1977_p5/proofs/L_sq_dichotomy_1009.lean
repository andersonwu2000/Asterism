-- Decomposition: the heavy lifting (which values x^2 can take when
-- x^2+y^2=1009 with |x|,|y|≤31) is pushed into `x_sq_in_225_784`.
-- Given that, the s9724 conclusion follows by simple linarith:
-- y^2 = 1009 - x^2 = 784 or 225 respectively.
import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs._strategy_s9724

namespace Problems.Minif2f.imo_1977_p5

def sq_dichotomy_1009 := @Problems.Minif2f.imo_1977_p5.s9724

end Problems.Minif2f.imo_1977_p5
