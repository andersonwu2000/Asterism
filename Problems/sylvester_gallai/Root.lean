-- s24155 (main): Kelly's 1948 proof — the minimiser pair (p, q) from
-- `exists_min_triple` has no third collinear point, since any such point
-- would let `descent_step` produce a strictly smaller minimiser via
-- `line_param_of_ne`'s parametrisation, contradicting `hmin`'s minimality.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s24155

namespace Problems.sylvester_gallai

def main := @Problems.sylvester_gallai.s24155

end Problems.sylvester_gallai
