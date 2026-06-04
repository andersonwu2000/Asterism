-- Decomposition: apply IVT to f(x) = x^(2^√2) - √2^(2^x) on [2,4].
-- f(2) ≥ 0 (since 2^(2^√2) ≥ 4 = √2^4) and f(4) ≤ 0 (since 2·2^√2 ≤ 8).
-- Continuity on [2,4] (positive base) lets IVT yield a root c ∈ [2,4].
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9680

namespace Problems.Minif2f.amc12b_2021_p21

def real_root_ge_two_exists := @Problems.Minif2f.amc12b_2021_p21.s9680

end Problems.Minif2f.amc12b_2021_p21
