-- Strip the `f` indirection via `hf` and reduce to a single math core:
-- prove primality of `k^2 + k + p` for all `i ≤ p-2`, given the same primality
-- on the small initial segment `k ≤ ⌊√(p/3)⌋`. The closed-form quadratic version
-- is strictly more abstract: it eliminates the unknown function `f` entirely.
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9294

namespace Problems.Minif2f.imo_1987_p6

def main := @Problems.Minif2f.imo_1987_p6.s9294

end Problems.Minif2f.imo_1987_p6
