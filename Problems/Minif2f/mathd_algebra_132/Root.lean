-- Direct leaf: substitute f, g into the composition equality and let nlinarith
-- finish. After rewriting h₂ : f (g x) = g (f x) becomes x^2 + 2 = (x+2)^2,
-- a linear-after-cancellation identity yielding x = -1/2.
import Mathlib
import Problems.Minif2f.mathd_algebra_132.Defs
import Problems.Minif2f.mathd_algebra_132.proofs._strategy_s637

namespace Problems.Minif2f.mathd_algebra_132

def main := @Problems.Minif2f.mathd_algebra_132.s637

end Problems.Minif2f.mathd_algebra_132
