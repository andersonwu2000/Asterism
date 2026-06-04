-- Decompose via t := x * sin x. Reduce to (a) positivity of x * sin x on (0, π)
-- and (b) the AM-GM-style core inequality 12 ≤ (9 t² + 4) / t for t > 0.
-- Algebraic glue: x² * (sin x)² = (x * sin x)², so the parent goal rewrites to
-- 12 ≤ (9 (x sin x)² + 4) / (x sin x), then the core lemma closes it.
import Mathlib
import Problems.Minif2f.aime_1983_p9.Defs
import Problems.Minif2f.aime_1983_p9.proofs._strategy_s534

namespace Problems.Minif2f.aime_1983_p9

def main := @Problems.Minif2f.aime_1983_p9.s534

end Problems.Minif2f.aime_1983_p9
